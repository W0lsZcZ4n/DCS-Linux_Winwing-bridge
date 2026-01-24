#!/usr/bin/env python3
"""
Setup Checker for WinWing DCS-BIOS Bridge
Verifies all requirements and configuration
"""
import os
import sys
import glob
import grp
import socket


class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 50}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 50}{Colors.RESET}\n")


def check_ok(msg):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def check_warn(msg):
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}")


def check_fail(msg):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


def check_python_version():
    """Check Python version"""
    print_header("Python Version")

    version = sys.version_info
    if version.major >= 3 and version.minor >= 6:
        check_ok(f"Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        check_fail(f"Python {version.major}.{version.minor}.{version.micro} (need 3.6+)")
        return False


def check_permissions():
    """Check user has access to HID devices"""
    print_header("Permissions")

    username = os.getenv('USER')
    try:
        user_groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]

        if 'input' in user_groups:
            check_ok(f"User '{username}' is in 'input' group")
            return True
        else:
            check_fail(f"User '{username}' NOT in 'input' group")
            print(f"   Run: sudo usermod -a -G input {username}")
            print(f"   Then log out and back in")
            return False
    except Exception as e:
        check_warn(f"Could not check groups: {e}")
        return False


def check_winwing_devices():
    """Check for connected WinWing devices"""
    print_header("WinWing Devices")

    devices_found = []

    # Device IDs to check
    device_ids = [
        (0x4098, 0xBF05, "PTO2 Panel"),
        (0x4098, 0xBD64, "Orion Throttle (F15EX)"),
        (0x4098, 0xBE62, "Orion Throttle (F18)"),
        (0x4098, 0xBEA8, "Orion Joystick (F16)"),
        (0x4098, 0xBEF0, "Skywalker Rudder"),
    ]

    for hidraw in glob.glob('/dev/hidraw*'):
        try:
            device_num = hidraw.split('hidraw')[1]
            info_path = f'/sys/class/hidraw/hidraw{device_num}/device/uevent'

            if os.path.exists(info_path):
                with open(info_path, 'r') as f:
                    uevent = f.read()

                for vid, pid, name in device_ids:
                    if f'HID_ID=0003:0000{vid:04X}:0000{pid:04X}' in uevent:
                        devices_found.append((name, hidraw))
                        check_ok(f"{name} at {hidraw}")
        except Exception as e:
            continue

    if not devices_found:
        check_warn("No WinWing devices found")
        print("   Connect your WinWing hardware via USB")
        return False

    return True


def check_dcs_installation():
    """Check DCS installation paths"""
    print_header("DCS Installation")

    dcs_path = os.path.expanduser("~/.local/share/Steam/steamapps/common/DCSWorld")
    dcs_user_path = os.path.expanduser("~/.local/share/Steam/steamapps/compatdata/223750/pfx/drive_c/users/steamuser/Saved Games/DCS")

    found = False

    if os.path.exists(dcs_path):
        check_ok(f"DCS installation found at {dcs_path}")
        found = True
    else:
        check_warn(f"DCS not found at {dcs_path}")

    if os.path.exists(dcs_user_path):
        check_ok(f"DCS user files found at {dcs_user_path}")
        found = True
    else:
        check_warn(f"DCS user files not found at {dcs_user_path}")

    return found


def check_dcsbios():
    """Check DCS-BIOS installation"""
    print_header("DCS-BIOS")

    dcsbios_path = os.path.expanduser("~/.local/share/Steam/steamapps/compatdata/223750/pfx/drive_c/users/steamuser/Saved Games/DCS/Scripts/DCS-BIOS")

    if os.path.exists(dcsbios_path):
        check_ok(f"DCS-BIOS found at {dcsbios_path}")

        # Check for export.lua
        export_lua = os.path.join(dcsbios_path, "lib", "ExportScript.lua")
        if os.path.exists(export_lua):
            check_ok("ExportScript.lua found")
        else:
            check_warn("ExportScript.lua not found")

        return True
    else:
        check_fail("DCS-BIOS not installed")
        print("   Install from: https://github.com/DCS-Skunkworks/dcs-bios")
        return False


def check_udp_port():
    """Check if UDP port 5010 multicast is available"""
    print_header("Network")

    try:
        # For multicast, we just check if we can create and bind a socket
        # Multiple processes can listen on the same multicast port
        import struct
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', 5010))

        # Test joining multicast group
        mreq = struct.pack('4sL', socket.inet_aton('239.255.50.10'), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        sock.close()
        check_ok("UDP port 5010 multicast is available")
        return True
    except OSError as e:
        check_fail(f"UDP port 5010 multicast setup failed: {e}")
        print("   Check firewall settings or network configuration")
        return False


def check_bridge_files():
    """Check if bridge files exist"""
    print_header("Bridge Files")

    required_files = [
        "winwing_bridge.py",
        "winwing_devices.py",
        "dcsbios_parser.py",
        "aircraft_mappings.py",
    ]

    all_exist = True
    for filename in required_files:
        if os.path.exists(filename):
            check_ok(f"{filename}")
        else:
            check_fail(f"{filename} NOT FOUND")
            all_exist = False

    return all_exist


def main():
    """Run all checks"""
    print(f"\n{Colors.BOLD}WinWing DCS-BIOS Bridge - Setup Checker{Colors.RESET}")

    results = []
    results.append(("Python Version", check_python_version()))
    results.append(("Bridge Files", check_bridge_files()))
    results.append(("Permissions", check_permissions()))
    results.append(("WinWing Devices", check_winwing_devices()))
    results.append(("DCS Installation", check_dcs_installation()))
    results.append(("DCS-BIOS", check_dcsbios()))
    results.append(("UDP Port", check_udp_port()))

    # Summary
    print_header("Summary")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if result else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"{name:20s} [{status}]")

    print(f"\n{Colors.BOLD}Status: {passed}/{total} checks passed{Colors.RESET}\n")

    if passed == total:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ Ready to run the bridge!{Colors.RESET}")
        print(f"\nNext steps:")
        print(f"  1. ./winwing_bridge.py --test-leds")
        print(f"  2. ./winwing_bridge.py --aircraft FA18C")
        return 0
    else:
        print(f"{Colors.YELLOW}⚠ Some checks failed - review issues above{Colors.RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
