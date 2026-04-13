import routeros_api
import time
from datetime import datetime

# ======================
# ROUTER CONFIG
# ======================
ROUTER_IP = "192.168.88.1"
USERNAME = "admin"
PASSWORD = "1945"

print("================================")
print(" MikroTik Auto-Setup Wizard")
print(" Time:", datetime.now())
print("================================")

try:
    connection = routeros_api.RouterOsApiPool(
        ROUTER_IP,
        username=USERNAME,
        password=PASSWORD,
        port=8728,
        plaintext_login=True
    )
    api = connection.get_api()

    # 1. SETUP SECURITY SHIELD (Firewall)
    print("\n[1] Setting up Security Shield...")
    fw_filter_api = api.get_resource('/ip/firewall/filter')
    filters = fw_filter_api.get()
    
    # Check if rule exists
    rule_exists = any(
        f.get('action') == 'drop' and f.get('src-address-list') == 'AUTO-BANNED'
        for f in filters
    )
    if not rule_exists:
        fw_filter_api.add(
            chain='input',
            action='drop',
            **{'src-address-list': 'AUTO-BANNED'},
            comment="Security Shield: Drop Auto-banned IPs"
        )
        print(" -> Created Drop rule for AUTO-BANNED list")
    else:
        print(" -> Drop rule already exists")

    # 2. SETUP FAILOVER GUARDIAN (Routes)
    print("\n[2] Setting up Failover Guardian (Routes)...")
    routes_api = api.get_resource('/ip/route')
    all_routes = routes_api.get()

    def ensure_route(gateway, comment, distance):
        if not any(r.get('comment') == comment for r in all_routes):
            try:
                routes_api.add(
                    gateway=gateway,
                    distance=distance,
                    comment=comment,
                    **{'check-gateway': 'ping'}
                )
                print(f" -> Created route for {comment} (Gateway: {gateway})")
            except Exception as e:
                print(f" -> Failed creating route {comment}: {e}")
        else:
             print(f" -> Route {comment} already exists")

    ensure_route("192.168.1.1", "ISP1_MAIN", "1")   # Example IP
    ensure_route("192.168.2.1", "ISP2_BACKUP", "2") # Example IP

    # 3. SETUP SMART QoS (Simple Queue)
    print("\n[3] Setting up Smart QoS Target Queue...")
    queue_api = api.get_resource('/queue/simple')
    if not any(q.get('name') == 'WiFi-Guest' for q in queue_api.get()):
        queue_api.add(
            name='WiFi-Guest',
            target='10.5.50.0/24', # Example Hotspot target IP
            **{'max-limit': '10M/10M'}
        )
        print(" -> Created queue 'WiFi-Guest'")
    else:
        print(" -> Queue 'WiFi-Guest' already exists")

    # 4. SETUP HOTSPOT & WIRELESS
    print("\n[4] Setting up Wireless Hotspot...")
    
    # Setup Wireless Interface
    wireless_api = api.get_resource('/interface/wireless')
    wlan1_list = [w for w in wireless_api.get() if w.get('name') == 'wlan1']
    if wlan1_list:
        wlan1 = wlan1_list[0]
        # Only set if it has an id
        if 'id' in wlan1:
            wireless_api.set(
                id=wlan1['id'],
                mode='ap-bridge',
                ssid='Magang',
                disabled='false'
            )
            print(" -> Configured wlan1 as AP Bridge (SSID: Magang)")
        else:
            print(" -> Interface wlan1 found but 'id' is missing. Skipping.")
    else:
        print(" -> Interface wlan1 not found. If this is a CHR/VM, wireless is not available.")

    # Setup Hotspot IP Address
    ip_address_api = api.get_resource('/ip/address')
    if not any(a.get('address') == '10.5.50.1/24' for a in ip_address_api.get()):
        ip_address_api.add(
            address='10.5.50.1/24',
            interface='wlan1',
            comment="Hotspot IP"
        )
        print(" -> Added IP 10.5.50.1/24 to wlan1")
    else:
        print(" -> IP 10.5.50.1/24 already exists")

    # Setup Hotspot Pool
    pool_api = api.get_resource('/ip/pool')
    if not any(p.get('name') == 'hs-pool-5' for p in pool_api.get()):
        pool_api.add(name='hs-pool-5', ranges='10.5.50.10-10.5.50.254')
        print(" -> Created IP Pool 'hs-pool-5'")

    # Remove wlan1 from bridge if it's a slave
    bridge_port_api = api.get_resource('/interface/bridge/port')
    wlan1_ports = [p for p in bridge_port_api.get() if p.get('interface') == 'wlan1']
    for p in wlan1_ports:
        print(" -> Removing wlan1 from bridge so it can be used for Hotspot standalone...")
        bridge_port_api.remove(id=p['id'])

    hs_interface = 'wlan1'

    # Setup DHCP Server for Hotspot
    dhcp_server_api = api.get_resource('/ip/dhcp-server')
    if not any(d.get('name') == 'dhcp-hs' for d in dhcp_server_api.get()):
        try:
            dhcp_server_api.add(
                name='dhcp-hs',
                interface=hs_interface,
                address_pool='hs-pool-5',
                disabled='false'
            )
            print(f" -> Created DHCP Server 'dhcp-hs' on {hs_interface}")
        except Exception as e:
            print(f" -> Failed to create DHCP server on {hs_interface}: {e}")
    else:
        print(" -> DHCP Server 'dhcp-hs' already exists")

    # Setup DHCP Network
    dhcp_net_api = api.get_resource('/ip/dhcp-server/network')
    if not any(n.get('address') == '10.5.50.0/24' for n in dhcp_net_api.get()):
         dhcp_net_api.add(
             address='10.5.50.0/24',
             gateway='10.5.50.1',
             dns_server='8.8.8.8,10.5.50.1'
         )
         print(" -> Created DHCP Network 10.5.50.0/24")
    else:
         print(" -> DHCP Network 10.5.50.0/24 already exists")

    # Create Hotspot Profile
    hs_profile_api = api.get_resource('/ip/hotspot/profile')
    if not any(p.get('name') == 'hsprof1' for p in hs_profile_api.get()):
        hs_profile_api.add(
            name='hsprof1',
            hotspot_address='10.5.50.1',
            dns_name='wifi.local'
        )
        print(" -> Created Hotspot Profile 'hsprof1'")
    else:
        print(" -> Hotspot Profile 'hsprof1' already exists")

    # Enable Hotspot Server
    hs_server_api = api.get_resource('/ip/hotspot')
    if not any(s.get('name') == 'hotspot1' for s in hs_server_api.get()):
        try:
            hs_server_api.add(
                name='hotspot1',
                interface=hs_interface,
                address_pool='hs-pool-5',
                profile='hsprof1',
                disabled='false'
            )
            print(f" -> Created Hotspot Server 'hotspot1' on {hs_interface}")
        except Exception as e:
            print(f" -> Failed to create Hotspot Server on {hs_interface}: {e}")
    else:
        print(" -> Hotspot Server 'hotspot1' already exists")

    # Add Default User
    hs_user_api = api.get_resource('/ip/hotspot/user')
    if not any(u.get('name') == 'guest' for u in hs_user_api.get()):
        hs_user_api.add(
            name='guest',
            password='guest',
            server='hotspot1'
        )
        print(" -> Created default hotspot user (guest:guest)")

    # API user
    user_api = api.get_resource('/user')
    if not any(u.get('name') == 'api_bot' for u in user_api.get()):
         user_api.add(
             name='api_bot',
             group='full',
             password='strong_api_password_123'
         )
         print(" -> Created dedicated 'api_bot' user for automation")

    # Setup NAT Masquerade for Hotspot to allow internet access
    print("\n[5] Setting up Internet Access for Hotspot...")
    nat_api = api.get_resource('/ip/firewall/nat')
    
    # Check if a masquerade rule for this specific source address exists
    if not any(n.get('src-address') == '10.5.50.0/24' and n.get('action') == 'masquerade' for n in nat_api.get()):
        try:
            nat_api.add(
                chain='srcnat',
                **{'src-address': '10.5.50.0/24'},
                action='masquerade',
                comment="Masquerade for Hotspot Network"
            )
            print(" -> Created NAT Masquerade rule for 10.5.50.0/24")
        except Exception as e:
            print(f" -> Failed to create NAT Masquerade: {e}")
    else:
        print(" -> NAT Masquerade rule for Hotspot already exists")

    connection.disconnect()
    
    print("\n✅ Setup Complete! MikroTik is ready for the overpowered scripts.")

except Exception as e:
    print(f"Error during setup: {e}")
