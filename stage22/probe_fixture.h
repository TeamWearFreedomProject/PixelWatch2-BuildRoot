/* Host fault-injection fixture, not code compiled into the watch kernel.
 * SPDX-License-Identifier: GPL-2.0-only
 */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define EPROBE_DEFER 517
#define GFP_KERNEL 0
#define DEFAULT_UTIL_FACTOR 100
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define struct_size(p, member, n) (sizeof(*(p)) + sizeof((p)->member[0]) * (n))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define WARN_ON(x) (!!(x))
#define dev_err(...) ((void)0)
#define dev_info(...) ((void)0)
#define dev_dbg(...) ((void)0)
#define pr_warn(...) ((void)0)
#define mutex_lock(p) ((void)(p))
#define mutex_unlock(p) ((void)(p))

struct list_head { struct list_head *next, *prev; };
#define LIST_HEAD(name) struct list_head name = { &name, &name }
static void INIT_LIST_HEAD(struct list_head *h) { h->next = h->prev = h; }
static bool list_empty(struct list_head *h) { return h->next == h; }
static void list_add_tail(struct list_head *n, struct list_head *h)
{
    struct list_head *prev = h->prev;
    /* Like CONFIG_DEBUG_LIST, touch both neighbours. ASan checks stale prev. */
    assert(prev->next == h);
    n->next = h; n->prev = prev; prev->next = n; h->prev = n;
}
static void list_del(struct list_head *n)
{
    assert(n->prev->next == n && n->next->prev == n);
    n->prev->next = n->next; n->next->prev = n->prev;
    n->next = n->prev = NULL;
}
#define container_of(p, type, member) ((type *)((char *)(p) - offsetof(type, member)))
#define list_for_each_entry_safe(pos, tmp, head, member) \
    for (struct list_head *_it = (head)->next, *_next; \
         _it != (head) && ((_next = _it->next), \
         (pos = container_of(_it, __typeof__(*pos), member)), \
         (tmp = _next == (head) ? NULL : container_of(_next, __typeof__(*tmp), member)), 1); \
         _it = _next)

struct device { void *of_node; };
struct platform_device { struct device dev; void *drvdata; };
struct clk_bulk_data { const char *id; };
struct icc_node {
    int id;
    const char *name;
    void *data;
    struct list_head node_list;
};
struct icc_onecell_data { size_t num_nodes; struct icc_node *nodes[]; };
struct icc_provider {
    struct device *dev;
    void (*set)(void), (*pre_aggregate)(void), (*aggregate)(void);
    void (*get_bw)(void), (*xlate)(void), (*xlate_extended)(void);
    struct list_head nodes, provider_list;
    void *data;
    int users;
};
struct qcom_icc_node;
struct noc_ops { void (*set_qos)(struct qcom_icc_node *); };
struct qosbox { bool initialized; };
struct qcom_icc_node {
    void *regmap;
    int id;
    const char *name;
    struct qosbox *qosbox;
    struct noc_ops *noc_ops;
    size_t num_links;
    int *links;
};
struct qcom_icc_desc { struct qcom_icc_node **nodes; size_t num_nodes; };
struct qcom_icc_provider {
    struct icc_provider provider;
    struct device *dev;
    struct clk_bulk_data *bus_clks, *qos_clks;
    int num_clks, num_qos_clks;
    bool init, keepalive;
    unsigned int util_factor;
    void *regmap;
    struct list_head probe_list;
};

static LIST_HEAD(icc_providers);
static LIST_HEAD(qnoc_probe_list);
static int icc_lock, probe_list_lock;
static const struct clk_bulk_data bus_clocks[] = { {"bus-a"}, {"bus-b"} };
static const char *fault;
static void *devres[16];
static size_t devres_count;
static int allocation, node_allocation, bus_live, qos_live, node_live;
static struct clk_bulk_data *bus_ptr, *qos_ptr;
static struct icc_node *node_by_id[4];
static struct qosbox boxes[2];
static void fixture_set_qos(struct qcom_icc_node *node) { (void)node; }
static struct noc_ops noc = { fixture_set_qos };
static struct qcom_icc_node qn0 = { .id=1, .name="first", .qosbox=&boxes[0], .noc_ops=&noc };
static struct qcom_icc_node qn1 = { .id=2, .name="second", .qosbox=&boxes[1], .noc_ops=&noc };
static struct qcom_icc_node *qnodes[] = { &qn0, NULL, &qn1 };
static struct qcom_icc_desc desc = { qnodes, ARRAY_SIZE(qnodes) };

static bool fails(const char *name) { return fault && !strcmp(fault, name); }
static void *fixture_alloc(size_t n)
{
    allocation++;
    if ((allocation == 1 && fails("alloc-qp")) ||
        (allocation == 2 && fails("alloc-data")) ||
        (allocation == 3 && fails("alloc-bus")) ||
        (allocation == 4 && fails("alloc-qos")))
        return NULL;
    void *p = calloc(1, n);
    assert(p && devres_count < ARRAY_SIZE(devres));
    devres[devres_count++] = p;
    return p;
}
static void fixture_release_devres(void)
{
    while (devres_count) free(devres[--devres_count]);
    bus_ptr = qos_ptr = NULL;
}
static void *devm_kzalloc(struct device *dev, size_t n, int flags)
{ return fixture_alloc(n); }
static void *devm_kmemdup(struct device *dev, const void *src, size_t n, int flags)
{
    void *p = fixture_alloc(n);
    if (p) memcpy(p, src, n);
    bus_ptr = p;
    return p;
}
static const struct qcom_icc_desc *of_device_get_match_data(struct device *dev)
{ return fails("no-desc") ? NULL : &desc; }
static int devm_clk_bulk_get(struct device *dev, int n, struct clk_bulk_data *clks)
{ return fails("bus-get") ? -EPROBE_DEFER : 0; }
static int devm_clk_bulk_get_all(struct device *dev, struct clk_bulk_data **clks)
{
    if (fails("qos-get-defer")) return -EPROBE_DEFER;
    if (fails("qos-get-eio")) return -EIO;
    if (fails("zero-qos")) { *clks = NULL; return 0; }
    qos_ptr = fixture_alloc(2 * sizeof(**clks));
    if (!qos_ptr) return -ENOMEM;
    *clks = qos_ptr;
    return 2;
}
static int clk_bulk_prepare_enable(int n, struct clk_bulk_data *clks)
{
    assert(n >= 0);
    if (!n) return 0;
    if (clks == bus_ptr) {
        if (fails("bus-enable")) return -EIO;
        bus_live += n;
    } else {
        assert(clks == qos_ptr);
        if (fails("qos-enable")) return -EIO;
        qos_live += n;
    }
    return 0;
}
static void clk_bulk_disable_unprepare(int n, struct clk_bulk_data *clks)
{
    assert(n >= 0);
    if (!n) return;
    if (clks == bus_ptr) { assert(bus_live >= n); bus_live -= n; }
    else { assert(clks == qos_ptr && qos_live >= n); qos_live -= n; }
}
static bool of_property_read_bool(void *np, const char *key) { return false; }
static int of_property_read_u32(void *np, const char *key, unsigned int *out)
{ return -EINVAL; }
static void *qcom_icc_map(struct platform_device *pdev, const struct qcom_icc_desc *d)
{ return fails("map") ? ERR_PTR(-EIO) : &desc; }
static void *dev_get_regmap(struct device *dev, const char *name) { return &desc; }
static void qcom_icc_rpm_set(void) {}
static void qcom_icc_rpm_pre_aggregate(void) {}
static void qcom_icc_rpm_aggregate(void) {}
static void qcom_icc_get_bw_stub(void) {}
static void of_icc_xlate_onecell(void) {}
static struct icc_node *icc_node_create(int id)
{
    node_allocation++;
    if ((node_allocation == 1 && fails("node-first")) ||
        (node_allocation == 2 && fails("node-second")))
        return ERR_PTR(-ENOMEM);
    assert(id > 0 && id < (int)ARRAY_SIZE(node_by_id) && !node_by_id[id]);
    struct icc_node *n = calloc(1, sizeof(*n));
    assert(n);
    n->id = id;
    node_by_id[id] = n;
    node_live++;
    return n;
}
static void icc_node_add(struct icc_node *node, struct icc_provider *provider)
{ list_add_tail(&node->node_list, &provider->nodes); }
static void icc_node_del(struct icc_node *node) { list_del(&node->node_list); }
static void icc_node_destroy(int id)
{
    assert(node_by_id[id]);
    free(node_by_id[id]); node_by_id[id] = NULL; node_live--;
}
static int icc_link_create(struct icc_node *node, int id) { return 0; }
static void platform_set_drvdata(struct platform_device *pdev, void *data)
{ pdev->drvdata = data; }
static int icc_provider_add(struct icc_provider *provider);
static int icc_provider_del(struct icc_provider *provider);
