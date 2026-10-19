#!/usr/bin/env python3
"""Read a flattened DT into a reduced PMIC-thermal dependency graph.

No overlay selection, hardware access, or register writes. Values are DT
declarations; provider presence does not prove that a driver will probe.
"""
import hashlib
import struct

COMPAT = "qcom,spmi-temp-alarm"


def cells(value):
    if len(value) % 4:
        raise ValueError("Property is not an array of u32 cells")
    return list(struct.unpack(">" + "I" * (len(value) // 4), value))


def strings(value):
    if not value:
        return []
    if not value.endswith(b"\0"):
        raise ValueError("Unterminated string property")
    return value[:-1].decode("utf-8").split("\0")


class Tree:
    def __init__(self, data):
        if len(data) < 40:
            raise ValueError("Truncated FDT header")
        magic, size, off, names_off, _, version, _, _, names_size, length = struct.unpack_from(">10I", data)
        if magic != 0xD00DFEED or version < 17 or not 40 <= size <= len(data):
            raise ValueError("Invalid/unsupported FDT")
        if off < 40 or names_off < 40 or off + length > size or names_off + names_size > size:
            raise ValueError("FDT section out of range")
        block, names = data[off:off + length], data[names_off:names_off + names_size]
        self.nodes, self.phandles = {}, {}
        stack, pos, ended = [], 0, False
        while pos + 4 <= len(block):
            token = struct.unpack_from(">I", block, pos)[0]
            pos += 4
            if token == 1:
                end = block.find(b"\0", pos)
                if end < 0 or len(stack) >= 128:
                    raise ValueError("Invalid FDT node")
                name = block[pos:end].decode("utf-8")
                pos = (end + 4) & ~3
                if "/" in name or (not stack and (name or self.nodes)):
                    raise ValueError("Invalid FDT root/node name")
                path = (stack[-1].rstrip("/") + "/" + name) if stack else "/"
                if path in self.nodes:
                    raise ValueError("Duplicate node")
                self.nodes[path] = {}
                stack.append(path)
            elif token == 2:
                if not stack:
                    raise ValueError("Unbalanced FDT")
                stack.pop()
            elif token == 3:
                if not stack or pos + 8 > len(block):
                    raise ValueError("Truncated FDT property")
                n, name_off = struct.unpack_from(">II", block, pos)
                pos += 8
                end = names.find(b"\0", name_off) if name_off < len(names) else -1
                if end < 0 or pos + n > len(block):
                    raise ValueError("FDT property out of bounds")
                key = names[name_off:end].decode("ascii")
                props = self.nodes[stack[-1]]
                if key in props:
                    raise ValueError("Duplicate property")
                props[key] = block[pos:pos + n]
                pos = (pos + n + 3) & ~3
            elif token == 4:
                continue
            elif token == 9:
                if stack or "/" not in self.nodes:
                    raise ValueError("Unbalanced FDT end")
                ended = True
                break
            else:
                raise ValueError("Unknown FDT token")
        if not ended:
            raise ValueError("FDT missing END")
        for path, props in self.nodes.items():
            values = [cells(props[key]) for key in ("phandle", "linux,phandle") if key in props]
            if not values:
                continue
            if any(len(v) != 1 or v[0] in (0, 0xFFFFFFFF) for v in values) or any(v != values[0] for v in values):
                raise ValueError("Invalid/conflicting phandle")
            phandle = values[0][0]
            if phandle in self.phandles:
                raise ValueError("Duplicate phandle")
            self.phandles[phandle] = path

    def ancestors(self, path):
        while True:
            yield path
            if path == "/":
                break
            path = path.rsplit("/", 1)[0] or "/"

    def describe(self, path):
        props = self.nodes[path]
        unavailable = [p for p in self.ancestors(path)
                       if strings(self.nodes[p].get("status", b"okay\0")) not in (["ok"], ["okay"])]
        return {"path": path, "compatible": strings(props.get("compatible", b"")),
                "declared_status": strings(props.get("status", b"")),
                "available_with_ancestors": not unavailable,
                "unavailable_ancestors_including_self": unavailable}

    def references(self, value, count_key):
        data, result, pos = cells(value), [], 0
        while pos < len(data):
            ph = data[pos]
            pos += 1
            if ph not in self.phandles:
                raise ValueError("Unresolved phandle " + hex(ph))
            path = self.phandles[ph]
            count = cells(self.nodes[path].get(count_key, b""))
            if len(count) != 1 or count[0] > 16 or pos + count[0] > len(data):
                raise ValueError("Missing/invalid provider " + count_key)
            result.append({"provider": self.describe(path), "args": data[pos:pos + count[0]]})
            pos += count[0]
        return result

    def interrupts(self, path):
        props = self.nodes[path]
        if "interrupts-extended" in props:
            return self.references(props["interrupts-extended"], "#interrupt-cells")
        current, visited = path, set()
        while current not in visited:
            visited.add(current)
            if "interrupt-parent" in self.nodes[current]:
                ph = cells(self.nodes[current]["interrupt-parent"])
                if len(ph) != 1 or ph[0] not in self.phandles:
                    raise ValueError("Unresolved interrupt-parent")
                provider = self.phandles[ph[0]]
            elif current != "/":
                provider = current.rsplit("/", 1)[0] or "/"
            else:
                break
            if "#interrupt-cells" in self.nodes[provider]:
                count = cells(self.nodes[provider].get("#interrupt-cells", b""))
                data = cells(props.get("interrupts", b""))
                if len(count) != 1 or not 0 < count[0] <= 16 or len(data) % count[0]:
                    raise ValueError("Invalid interrupt specifier")
                return [{"provider": self.describe(provider), "args": data[i:i + count[0]]}
                        for i in range(0, len(data), count[0])]
            current = provider
        raise ValueError("Interrupt controller unresolved or cyclic")


def graph(data):
    tree = Tree(data)
    alarms = []
    for path, props in tree.nodes.items():
        if COMPAT not in strings(props.get("compatible", b"")):
            continue
        item = tree.describe(path)
        item["reg_cells"] = cells(props.get("reg", b""))
        item["thermal_sensor_cells"] = cells(props.get("#thermal-sensor-cells", b""))
        item["ancestors"] = [tree.describe(p) for p in list(tree.ancestors(path))[1:]]
        item["issues"] = []
        try:
            item["interrupts"] = tree.interrupts(path)
        except ValueError as e:
            item["interrupts"] = []
            item["issues"].append(str(e))
        try:
            refs = tree.references(props.get("io-channels", b""), "#io-channel-cells")
            names = strings(props.get("io-channel-names", b""))
            item["iio_channels"] = [{**ref, "name": names[i] if i < len(names) else None}
                                    for i, ref in enumerate(refs)]
            if len(names) != len(refs):
                item["issues"].append("IIO name/channel count differs")
        except ValueError as e:
            item["iio_channels"] = []
            item["issues"].append(str(e))
        item["thermal_zones"] = []
        for zone, zprops in tree.nodes.items():
            if "thermal-sensors" not in zprops:
                continue
            try:
                refs = tree.references(zprops["thermal-sensors"], "#thermal-sensor-cells")
            except ValueError as e:
                item["issues"].append(zone + ": " + str(e))
                continue
            for ref in refs:
                if ref["provider"]["path"] != path:
                    continue
                z = {**tree.describe(zone), "sensor_args": ref["args"], "trips": []}
                z["matches_driver_sensor_id_0"] = not ref["args"] or ref["args"][0] == 0
                for trip, tprops in tree.nodes.items():
                    if trip.rsplit("/", 1)[0] != zone + "/trips":
                        continue
                    z["trips"].append({"path": trip, "type": strings(tprops.get("type", b"")),
                                       "temperature_mC": cells(tprops.get("temperature", b"")),
                                       "hysteresis_mC": cells(tprops.get("hysteresis", b""))})
                item["thermal_zones"].append(z)
        item["adc_declaration"] = ("NAMED_THERMAL_IIO_CHANNEL" if any(c["name"] == "thermal" for c in item["iio_channels"])
                                   else "NO_NAMED_THERMAL_CHANNEL_DRIVER_CAN_ESTIMATE")
        if not item["reg_cells"]:
            item["issues"].append("Missing required reg")
        if not item["interrupts"]:
            item["issues"].append("Missing/unresolved required IRQ")
        if not any(z["available_with_ancestors"] and z["matches_driver_sensor_id_0"] for z in item["thermal_zones"]):
            item["issues"].append("No available thermal-zone reference for driver sensor ID 0")
        alarms.append(item)
    return {"dtb_sha256": hashlib.sha256(data).hexdigest(),
            "root_compatible": strings(tree.nodes["/"].get("compatible", b"")),
            "thermal_alarms": alarms,
            "runtime_probe": "NOT_TESTED", "battery_temperature_verified": False}
