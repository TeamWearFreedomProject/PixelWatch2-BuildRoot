/* Included after the actual pinned qnoc_probe function by run_probe_tests.py.
 * Fixture teardown below is not a test of the production qnoc_remove path.
 * SPDX-License-Identifier: GPL-2.0-only
 */
static void assert_clean(struct platform_device *pdev)
{
    assert(list_empty(&icc_providers));
    assert(list_empty(&qnoc_probe_list));
    assert(!bus_live && !qos_live && !node_live && !pdev->drvdata);
}

static void release_success_fixture(struct platform_device *pdev)
{
    struct qcom_icc_provider *qp = pdev->drvdata;
    struct icc_node *n, *tmp;
    assert(qp && bus_live == 2 && qos_live == 0 && node_live == 2);
    assert(qp->provider.data && ((struct icc_onecell_data *)qp->provider.data)->num_nodes == 3);
    list_for_each_entry_safe(n, tmp, &qp->provider.nodes, node_list) {
        icc_node_del(n);
        icc_node_destroy(n->id);
    }
    assert(icc_provider_del(&qp->provider) == 0);
    clk_bulk_disable_unprepare(qp->num_clks, qp->bus_clks);
    list_del(&qp->probe_list);
    pdev->drvdata = NULL;
    fixture_release_devres();
    assert_clean(pdev);
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    struct platform_device pdev = {0};
    fault = argv[1];
    if (!strcmp(fault, "retry-qos-get") || !strcmp(fault, "retry-qos-enable")) {
        bool get_failure = !strcmp(fault, "retry-qos-get");
        fault = get_failure ? "qos-get-defer" : "qos-enable";
        for (int i = 0; i < 16; i++) {
            allocation = node_allocation = 0;
            int ret = qnoc_probe(&pdev);
            assert(ret == (get_failure ? -EPROBE_DEFER : -EIO));
            /* Model driver-core devres release after each failed probe.
             * Leave list inspection until the next attempt in the negative
             * control, so the original stale link is diagnosed by ASan. */
            fixture_release_devres();
            if (!getenv("AURORA_NEGATIVE_CONTROL")) assert_clean(&pdev);
        }
        fault = "success";
        allocation = node_allocation = 0;
        assert(qnoc_probe(&pdev) == 0);
        release_success_fixture(&pdev);
    } else {
        int ret = qnoc_probe(&pdev);
        if (fails("success") || fails("zero-qos")) {
            assert(ret == 0);
            release_success_fixture(&pdev);
        } else {
            int expected = -EIO;
            if (fails("no-desc")) expected = -EINVAL;
            if (!strncmp(fault, "alloc-", 6) || !strncmp(fault, "node-", 5)) expected = -ENOMEM;
            if (fails("bus-get") || fails("qos-get-defer")) expected = -EPROBE_DEFER;
            assert(ret == expected);
            fixture_release_devres();
            assert_clean(&pdev);
        }
    }
    puts("PASS");
    return 0;
}
