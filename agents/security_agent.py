import os
import socket
import subprocess
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

class SecurityAgent:
    """
    Trinity Security Agent
    Monitors Trinity6 network security
    Scans for unknown devices
    Checks for vulnerabilities
    Runs on Raspberry Pi 24/7
    Full scan on desktop when available
    """
    
    def __init__(self, memory=None):
        self.memory = memory
        self.known_devices = []
        self.scan_results = {}
    
    # ==========================================
    # NETWORK SCANNING
    # ==========================================
    
    def get_local_network(self):
        """Detect local network range"""
        try:
            s = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM
            )
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            parts = local_ip.split('.')
            network = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
            return network, local_ip
            
        except Exception as e:
            print(f"Error detecting network: {str(e)}")
            return "192.168.1.0/24", "unknown"
    
    def ping_host(self, ip):
        """Check if host is alive"""
        try:
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '1', str(ip)],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except:
            return False
    
    def get_hostname(self, ip):
        """Get hostname for IP"""
        try:
            return socket.gethostbyaddr(ip)[0]
        except:
            return "Unknown"
    
    def check_port(self, ip, port):
        """Check if port is open"""
        try:
            sock = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            )
            sock.settimeout(1)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def scan_device(self, ip):
        """Scan a single device"""
        if not self.ping_host(ip):
            return None
        
        hostname = self.get_hostname(ip)
        
        ports_to_check = {
            22: 'SSH',
            23: 'Telnet',
            80: 'HTTP',
            443: 'HTTPS',
            445: 'SMB',
            3389: 'RDP',
            8080: 'HTTP-Alt'
        }
        
        open_ports = {}
        for port, service in ports_to_check.items():
            if self.check_port(ip, port):
                open_ports[port] = service
        
        risk_level = 'low'
        risks = []
        
        if 23 in open_ports:
            risk_level = 'high'
            risks.append('Telnet is open - insecure protocol')
        if 3389 in open_ports:
            risk_level = 'medium'
            risks.append('RDP exposed - brute force risk')
        if 445 in open_ports:
            risks.append('SMB exposed - check for vulnerabilities')
        
        return {
            'ip': str(ip),
            'hostname': hostname,
            'open_ports': open_ports,
            'risk_level': risk_level,
            'risks': risks,
            'scan_time': datetime.now().isoformat()
        }
    
    def scan_network(self, network_range=None):
        """Scan entire network for devices"""
        import ipaddress
        
        if not network_range:
            network_range, local_ip = self.get_local_network()
        
        print(f"Scanning network: {network_range}")
        
        network = ipaddress.IPv4Network(
            network_range, strict=False
        )
        hosts = list(network.hosts())
        
        devices = []
        with ThreadPoolExecutor(max_workers=50) as executor:
            results = executor.map(
                lambda ip: self.scan_device(str(ip)),
                hosts
            )
            devices = [r for r in results if r is not None]
        
        self.scan_results = {
            'network': network_range,
            'scan_time': datetime.now().isoformat(),
            'total_devices': len(devices),
            'devices': devices
        }
        
        return devices
    
    # ==========================================
    # THREAT DETECTION
    # ==========================================
    
    def detect_unknown_devices(self, current_devices):
        """Detect devices not seen before"""
        known_ips = [d['ip'] for d in self.known_devices]
        
        unknown = [
            d for d in current_devices
            if d['ip'] not in known_ips
        ]
        
        return unknown
    
    def detect_high_risk_devices(self, devices):
        """Find devices with security risks"""
        return [
            d for d in devices
            if d.get('risk_level') in ['high', 'medium']
            and d.get('risks')
        ]
    
    def check_ssl_certificate(self, domain="trinity6.com"):
        """Check SSL certificate validity"""
        try:
            import ssl
            import socket
            
            context = ssl.create_default_context()
            conn = context.wrap_socket(
                socket.socket(socket.AF_INET),
                server_hostname=domain
            )
            conn.settimeout(5)
            conn.connect((domain, 443))
            cert = conn.getpeercert()
            conn.close()
            
            expire_date = datetime.strptime(
                cert['notAfter'],
                '%b %d %H:%M:%S %Y %Z'
            )
            
            days_until_expiry = (
                expire_date - datetime.now()
            ).days
            
            return {
                'domain': domain,
                'valid': True,
                'expires': str(expire_date),
                'days_until_expiry': days_until_expiry,
                'needs_renewal': days_until_expiry < 30
            }
            
        except Exception as e:
            return {
                'domain': domain,
                'valid': False,
                'error': str(e)
            }
    
    # ==========================================
    # SECURITY REPORT
    # ==========================================
    
    def run_security_check(self):
        """Run complete security check"""
        print("Trinity running security check...")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'overall_risk': 'low',
            'alerts': [],
            'network_scan': None,
            'ssl_check': None,
            'recommendations': []
        }
        
        print("Checking SSL certificate...")
        ssl_result = self.check_ssl_certificate()
        report['ssl_check'] = ssl_result
        
        if not ssl_result.get('valid'):
            report['alerts'].append(
                "SSL certificate invalid for trinity6.com"
            )
            report['overall_risk'] = 'high'
        elif ssl_result.get('days_until_expiry', 999) < 30:
            report['alerts'].append(
                f"SSL certificate expires in {ssl_result['days_until_expiry']} days"
            )
            report['overall_risk'] = 'medium'
        
        print("Scanning network...")
        try:
            devices = self.scan_network()
            report['network_scan'] = {
                'total_devices': len(devices),
                'devices': devices
            }
            
            high_risk = self.detect_high_risk_devices(devices)
            if high_risk:
                report['overall_risk'] = 'high'
                for device in high_risk:
                    for risk in device.get('risks', []):
                        report['alerts'].append(
                            f"{device['ip']}: {risk}"
                        )
            
            unknown = self.detect_unknown_devices(devices)
            if unknown:
                report['alerts'].append(
                    f"{len(unknown)} unknown devices found on network"
                )
                for device in unknown:
                    report['alerts'].append(
                        f"Unknown device: {device['ip']} - {device['hostname']}"
                    )
        
        except Exception as e:
            report['alerts'].append(
                f"Network scan error: {str(e)}"
            )
        
        if not report['alerts']:
            report['recommendations'].append(
                "Network looks clean. No threats detected."
            )
        else:
            report['recommendations'].append(
                "Review flagged devices and resolve alerts."
            )
        
        if self.memory:
            self.memory.update_monitoring_status(
                'network_status',
                report['overall_risk']
            )
            
            for alert in report['alerts']:
                self.memory.add_alert(
                    'security',
                    alert,
                    report['overall_risk']
                )
        
        return report
    
    def get_security_summary(self):
        """Get brief security summary"""
        if not self.scan_results:
            return "No scan results available yet."
        
        devices = self.scan_results.get('devices', [])
        high_risk = self.detect_high_risk_devices(devices)
        
        return {
            'total_devices': len(devices),
            'high_risk_devices': len(high_risk),
            'overall_status': 'clean' if not high_risk else 'threats detected',
            'last_scan': self.scan_results.get('scan_time')
        }
