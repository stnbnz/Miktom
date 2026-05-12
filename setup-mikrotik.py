import argparse
import os
import sys
from datetime import datetime

import django
import routeros_api

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_monitor"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web_monitor.settings")
django.setup()

from dashboard.models import ActivityLog, Router


def get_item_id(item):
    return item.get(".id") or item.get("id")


def truthy(value):
    return str(value).lower() in ("true", "yes", "1")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Setup MikroTik from scratch until hotspot is active."
    )
    parser.add_argument("router_ip", nargs="?")
    parser.add_argument("username", nargs="?")
    parser.add_argument("password", nargs="?")
    parser.add_argument("--port", type=int, default=8728)
    parser.add_argument("--lan-interface", default="wlan1")
    parser.add_argument("--wan-interface", default="ether1")
    parser.add_argument("--ssid", default="MikroTik-Hotspot")
    parser.add_argument("--hotspot-network", default="10.5.50.0/24")
    parser.add_argument("--hotspot-gateway", default="10.5.50.1/24")
    parser.add_argument("--pool-range", default="10.5.50.10-10.5.50.254")
    parser.add_argument("--dns", default="8.8.8.8,1.1.1.1")
    parser.add_argument("--guest-user", default="guest")
    parser.add_argument("--guest-pass", default="guest")
    parser.add_argument("--pppoe-network", default="10.5.51.0/24")
    parser.add_argument("--pppoe-gateway", default="10.5.51.1")
    parser.add_argument("--pppoe-pool-range", default="10.5.51.10-10.5.51.254")
    parser.add_argument("--pppoe-interface", default="ether2")
    parser.add_argument("--pppoe-user", default="pppoe-test")
    parser.add_argument("--pppoe-pass", default="pppoe-test")
    return parser.parse_args()


def main():
    args = parse_args()
    print("================================")
    print(" MikroTik Auto-Setup Wizard")
    print(" Time:", datetime.now())
    print("================================")

    if args.router_ip and args.username is not None and args.password is not None:
        router, _ = Router.objects.get_or_create(
            ip_address=args.router_ip,
            defaults={
                "name": f"Router_{args.router_ip}",
                "username": args.username,
                "password": args.password,
                "port": args.port,
            },
        )
        if router.username != args.username or router.password != args.password or router.port != args.port:
            router.username = args.username
            router.password = args.password
            router.port = args.port
            router.save(update_fields=["username", "password", "port"])
    else:
        router = Router.objects.first()
        if not router:
            print("Error: No router configured.")
            print("Usage: python setup-mikrotik.py <IP> <USERNAME> <PASSWORD>")
            return 1

    print(f"Configuring router: {router.name} ({router.ip_address})")

    connection = None
    try:
        connection = routeros_api.RouterOsApiPool(
            router.ip_address,
            username=router.username,
            password=router.password,
            port=router.port,
            plaintext_login=True,
        )
        api = connection.get_api()

        fw_filter_api = api.get_resource("/ip/firewall/filter")
        routes_api = api.get_resource("/ip/route")
        queue_api = api.get_resource("/queue/simple")
        wireless_api = api.get_resource("/interface/wireless")
        bridge_port_api = api.get_resource("/interface/bridge/port")
        ip_address_api = api.get_resource("/ip/address")
        pool_api = api.get_resource("/ip/pool")
        dhcp_server_api = api.get_resource("/ip/dhcp-server")
        dhcp_net_api = api.get_resource("/ip/dhcp-server/network")
        hs_profile_api = api.get_resource("/ip/hotspot/profile")
        hs_server_api = api.get_resource("/ip/hotspot")
        hs_user_api = api.get_resource("/ip/hotspot/user")
        nat_api = api.get_resource("/ip/firewall/nat")
        user_api = api.get_resource("/user")
        ppp_profile_api = api.get_resource("/ppp/profile")
        pppoe_server_api = api.get_resource("/interface/pppoe-server/server")
        ppp_secret_api = api.get_resource("/ppp/secret")

        print("\n[1] Setting up Security Shield...")
        existing_filters = fw_filter_api.get()
        if not any(f.get("action") == "drop" and f.get("src-address-list") == "AUTO-BANNED" for f in existing_filters):
            fw_filter_api.add(
                chain="input",
                action="drop",
                **{"src-address-list": "AUTO-BANNED"},
                comment="Security Shield: Drop Auto-banned IPs",
            )
            print(" -> Created drop rule for AUTO-BANNED")
        else:
            print(" -> Drop rule already exists")

        print("\n[2] Setting up failover routes...")
        existing_routes = routes_api.get()
        if not any(r.get("comment") == "ISP1_MAIN" for r in existing_routes):
            routes_api.add(gateway="192.168.88.1", distance="1", comment="ISP1_MAIN", **{"check-gateway": "ping"})
            print(" -> Added ISP1_MAIN route")
        if not any(r.get("comment") == "ISP2_BACKUP" for r in existing_routes):
            routes_api.add(gateway="192.168.2.1", distance="2", comment="ISP2_BACKUP", **{"check-gateway": "ping"})
            print(" -> Added ISP2_BACKUP route")

        print("\n[3] Setting up Smart QoS...")
        queues = queue_api.get()
        if not any(q.get("name") == "WiFi-Guest" for q in queues):
            queue_api.add(name="WiFi-Guest", target=args.hotspot_network, **{"max-limit": "10M/10M"})
            print(" -> Created queue WiFi-Guest")
        else:
            print(" -> Queue WiFi-Guest already exists")

        print("\n[4] Setting up hotspot from zero...")
        interfaces = api.get_resource("/interface").get()
        interface_names = {i.get("name") for i in interfaces}
        hs_interface = args.lan_interface if args.lan_interface in interface_names else "bridge"

        wlan = [w for w in wireless_api.get() if w.get("name") == args.lan_interface]
        if wlan:
            wlan_id = get_item_id(wlan[0])
            if wlan_id:
                wireless_api.set(**{".id": wlan_id, "mode": "ap-bridge", "ssid": args.ssid, "disabled": "false"})
                print(f" -> Wireless configured: {args.lan_interface} ({args.ssid})")

        for port in bridge_port_api.get():
            if port.get("interface") == args.lan_interface:
                pid = get_item_id(port)
                if pid:
                    bridge_port_api.remove(**{".id": pid})
                    print(f" -> Removed {args.lan_interface} from bridge")

        if not any(a.get("address") == args.hotspot_gateway for a in ip_address_api.get()):
            ip_address_api.add(address=args.hotspot_gateway, interface=hs_interface, comment="Hotspot IP")
            print(f" -> Added IP {args.hotspot_gateway} on {hs_interface}")

        if not any(p.get("name") == "hs-pool-main" for p in pool_api.get()):
            pool_api.add(name="hs-pool-main", ranges=args.pool_range)
            print(" -> Created pool hs-pool-main")

        if not any(d.get("name") == "dhcp-hs" for d in dhcp_server_api.get()):
            dhcp_server_api.add(name="dhcp-hs", interface=hs_interface, address_pool="hs-pool-main", disabled="false")
            print(" -> Created DHCP server dhcp-hs")

        if not any(n.get("address") == args.hotspot_network for n in dhcp_net_api.get()):
            gateway_ip = args.hotspot_gateway.split("/")[0]
            dhcp_net_api.add(address=args.hotspot_network, gateway=gateway_ip, dns_server=args.dns)
            print(f" -> Created DHCP network {args.hotspot_network}")

        if not any(p.get("name") == "hsprof-main" for p in hs_profile_api.get()):
            hs_profile_api.add(name="hsprof-main", hotspot_address=args.hotspot_gateway.split("/")[0], dns_name="wifi.local")
            print(" -> Created hotspot profile hsprof-main")

        if not any(s.get("name") == "hotspot1" for s in hs_server_api.get()):
            hs_server_api.add(
                name="hotspot1",
                interface=hs_interface,
                address_pool="hs-pool-main",
                profile="hsprof-main",
                disabled="false",
            )
            print(f" -> Created hotspot server on {hs_interface}")
        else:
            for srv in hs_server_api.get():
                if srv.get("name") == "hotspot1" and truthy(srv.get("disabled", "false")):
                    sid = get_item_id(srv)
                    if sid:
                        hs_server_api.set(**{".id": sid, "disabled": "false"})
                        print(" -> Enabled existing hotspot1")

        users = hs_user_api.get()
        if not any(u.get("name") == args.guest_user for u in users):
            hs_user_api.add(name=args.guest_user, password=args.guest_pass, server="hotspot1")
            print(f" -> Created hotspot user {args.guest_user}")

        print("\n[5] Setting up NAT masquerade...")
        nat_rules = nat_api.get()
        if not any(
            n.get("chain") == "srcnat"
            and n.get("action") == "masquerade"
            and n.get("out-interface") == args.wan_interface
            for n in nat_rules
        ):
            nat_api.add(
                chain="srcnat",
                action="masquerade",
                **{"out-interface": args.wan_interface},
                comment="Masquerade for internet",
            )
            print(f" -> Created NAT masquerade on {args.wan_interface}")

        if not any(
            n.get("chain") == "srcnat"
            and n.get("action") == "masquerade"
            and n.get("src-address") == args.hotspot_network
            for n in nat_rules
        ):
            nat_api.add(
                chain="srcnat",
                action="masquerade",
                **{"src-address": args.hotspot_network},
                comment="Masquerade for hotspot network",
            )
            print(f" -> Created NAT masquerade for {args.hotspot_network}")

        print("\n[6] Creating API user...")
        if not any(u.get("name") == "api_bot" for u in user_api.get()):
            user_api.add(name="api_bot", group="full", password="strong_api_password_123")
            print(" -> Created api_bot user")
        else:
            print(" -> api_bot already exists")

        print("\n[7] Setting up PPPoE server...")
        if not any(p.get("name") == "pppoe-pool-main" for p in pool_api.get()):
            pool_api.add(name="pppoe-pool-main", ranges=args.pppoe_pool_range)
            print(" -> Created pool pppoe-pool-main")

        if not any(p.get("name") == "pppoe-profile-main" for p in ppp_profile_api.get()):
            ppp_profile_api.add(
                name="pppoe-profile-main", 
                **{"local-address": args.pppoe_gateway, "remote-address": "pppoe-pool-main", "dns-server": args.dns}
            )
            print(" -> Created PPPoE profile pppoe-profile-main")

        if not any(s.get("service-name") == "pppoe-main" for s in pppoe_server_api.get()):
            try:
                pppoe_server_api.add(
                    **{"service-name": "pppoe-main", "default-profile": "pppoe-profile-main", "disabled": "false"},
                    interface=args.pppoe_interface
                )
                print(f" -> Created PPPoE server on {args.pppoe_interface}")
            except Exception as e:
                print(f" -> Warning: Failed to create PPPoE server (maybe interface {args.pppoe_interface} doesn't exist): {e}")
        else:
            for srv in pppoe_server_api.get():
                if srv.get("service-name") == "pppoe-main" and truthy(srv.get("disabled", "false")):
                    sid = get_item_id(srv)
                    if sid:
                        pppoe_server_api.set(**{".id": sid, "disabled": "false"})
                        print(" -> Enabled existing pppoe-main server")

        if not any(u.get("name") == args.pppoe_user for u in ppp_secret_api.get()):
            ppp_secret_api.add(
                name=args.pppoe_user, 
                password=args.pppoe_pass, 
                profile="pppoe-profile-main", 
                service="pppoe"
            )
            print(f" -> Created PPPoE test user {args.pppoe_user}")

        # Re-fetch NAT rules to check if PPPoE NAT exists
        nat_rules = nat_api.get()
        if not any(
            n.get("chain") == "srcnat"
            and n.get("action") == "masquerade"
            and n.get("src-address") == args.pppoe_network
            for n in nat_rules
        ):
            nat_api.add(
                chain="srcnat",
                action="masquerade",
                **{"src-address": args.pppoe_network},
                comment="Masquerade for PPPoE network",
            )
            print(f" -> Created NAT masquerade for {args.pppoe_network}")

        ActivityLog.objects.create(
            router=router,
            activity_type="qos_change",
            description="MikroTik setup wizard completed until hotspot active",
            success=True,
            metadata={
                "lan_interface": hs_interface,
                "wan_interface": args.wan_interface,
                "hotspot_network": args.hotspot_network,
                "pppoe_network": args.pppoe_network,
            },
        )
        print("\n✅ Setup complete. Hotspot, PPPoE, and base automation config are ready.")
        return 0
    except Exception as e:
        print(f"Error during setup: {e}")
        ActivityLog.objects.create(
            router=router,
            activity_type="system_reset",
            description="MikroTik setup wizard failed",
            metadata={"error": str(e)},
            success=False,
            error_message=str(e),
        )
        return 1
    finally:
        if connection:
            try:
                connection.disconnect()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
