"""
test the SRS DG-645 digital delay device support

Hardware is not available so test with best efforts
"""

from ..instrument import delay


async def test_dg645_device():
    dg645 = delay.DG645Delay("", name="delay")
    await dg645.connect(mock=True)
    read_names = []
    read_attrs = (await dg645.describe()).keys()
    assert sorted(read_attrs) == read_names

    cfg_names = [
        "delay-burst_config",
        "delay-burst_count",
        "delay-burst_delay",
        "delay-burst_mode",
        "delay-burst_period",
        "delay-channels-A-reference",
        "delay-channels-A-delay",
        "delay-channels-B-reference",
        "delay-channels-B-delay",
        "delay-channels-C-reference",
        "delay-channels-C-delay",
        "delay-channels-D-reference",
        "delay-channels-D-delay",
        "delay-channels-E-reference",
        "delay-channels-E-delay",
        "delay-channels-F-reference",
        "delay-channels-F-delay",
        "delay-channels-G-reference",
        "delay-channels-G-delay",
        "delay-channels-H-reference",
        "delay-channels-H-delay",
        "delay-device_id",
        "delay-label",
        "delay-outputs-AB-amplitude",
        "delay-outputs-AB-offset",
        "delay-outputs-AB-polarity",
        "delay-outputs-AB-trigger_phase",
        "delay-outputs-AB-trigger_prescale",
        "delay-outputs-CD-amplitude",
        "delay-outputs-CD-offset",
        "delay-outputs-CD-polarity",
        "delay-outputs-CD-trigger_phase",
        "delay-outputs-CD-trigger_prescale",
        "delay-outputs-EF-amplitude",
        "delay-outputs-EF-offset",
        "delay-outputs-EF-polarity",
        "delay-outputs-EF-trigger_phase",
        "delay-outputs-EF-trigger_prescale",
        "delay-outputs-GH-amplitude",
        "delay-outputs-GH-offset",
        "delay-outputs-GH-polarity",
        "delay-outputs-GH-trigger_phase",
        "delay-outputs-GH-trigger_prescale",
        "delay-outputs-T0-amplitude",
        "delay-outputs-T0-offset",
        "delay-outputs-T0-polarity",
        "delay-trigger_advanced_mode",
        "delay-trigger_holdoff",
        "delay-trigger_inhibit",
        "delay-trigger_level",
        "delay-trigger_prescale",
        "delay-trigger_rate",
        "delay-trigger_source",
    ]
    cfg_attrs = (await dg645.describe_configuration()).keys()
    assert sorted(cfg_attrs) == sorted(cfg_names)

    # List all the components
    cpt_names = [
        "delay-autoip_state",
        "delay-bare_socket_state",
        "delay-burst_config",
        "delay-burst_count",
        "delay-burst_delay",
        "delay-burst_mode",
        "delay-burst_period",
        "delay-channels",
        "delay-clear_error",
        "delay-device_id",
        "delay-dhcp_state",
        "delay-gateway",
        "delay-goto_local",
        "delay-goto_remote",
        "delay-gpib_address",
        "delay-gpib_state",
        "delay-ip_address",
        "delay-label",
        "delay-lan_state",
        "delay-mac_address",
        "delay-network_mask",
        "delay-outputs",
        "delay-reset",
        "delay-reset_gpib",
        "delay-reset_lan",
        "delay-reset_serial",
        "delay-serial_baud",
        "delay-serial_state",
        "delay-static_ip_state",
        "delay-status",
        "delay-status_checking",
        "delay-telnet_state",
        "delay-trigger_advanced_mode",
        "delay-trigger_holdoff",
        "delay-trigger_inhibit",
        "delay-trigger_level",
        "delay-trigger_prescale",
        "delay-trigger_rate",
        "delay-trigger_source",
        "delay-vxi11_state",
    ]
    child_names = [child.name for attr, child in dg645.children()]
    assert sorted(child_names) == sorted(cpt_names)
