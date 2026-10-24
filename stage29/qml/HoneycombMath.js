.pragma library

// Axial hexagons in expanding rings; screen projection has a shrinking radial
// derivative, so the periphery contracts continuously as the canvas is panned.
function cells(count) {
    var out = [{q: 0, r: 0}]
    var directions = [[1,0],[0,1],[-1,1],[-1,0],[0,-1],[1,-1]]
    for (var ring = 1; out.length < count; ++ring) {
        var q = 0, r = -ring
        for (var side = 0; side < 6 && out.length < count; ++side)
            for (var step = 0; step < ring && out.length < count; ++step) {
                out.push({q:q, r:r})
                q += directions[side][0]; r += directions[side][1]
            }
    }
    return out
}
function logical(cell) { return {x: (cell.q + cell.r / 2) * 100, y: cell.r * 86.6025403784} }
function project(cell, panX, panY) {
    var p = logical(cell), x = p.x + panX, y = p.y + panY
    var d = Math.sqrt(x*x+y*y), e = Math.exp(2*Math.min(d/190, 8))
    var t = (e-1)/(e+1), scale = 1-t*t
    var f = d > 0 ? 190*t/d : 1
    return {x:192+x*f, y:192+y*f, scale:scale, diameter:84*scale,
            opacity: Math.max(0, Math.min(1,(scale-0.045)/0.14))}
}
function clamp(value, limit) { return Math.max(-limit, Math.min(limit, value)) }
