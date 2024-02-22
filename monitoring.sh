#!/usr/bin/bash
#
# Enhanced monitoring functionality; Tested on Amazon Linux 2023.
#

# Fetch EC2 Instance Metadata
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
AZ=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/availability-zone)
INSTANCE_TYPE=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-type)

# Memory Usage
MEMORYUSAGE=$(free -m | awk 'NR==2{printf "%.2f%%", $3*100/$2 }')

# CPU Load Average
CPU_LOAD=$(top -bn1 | grep "load average:" | awk '{print $10 $11 $12}')

# Disk Usage
DISK_USAGE=$(df -BG | awk '$NF=="/"{printf "Total: %s, Used: %s, Available: %s", $2, $3, $4}')

# Number of Processes
PROCESSES=$(expr $(ps -A | grep -c .) - 1)

# Check for HTTPD (Apache) Processes
HTTPD_PROCESSES=$(ps -A | grep -c httpd)

# Network Statistics
NETWORK_TX=$(cat /sys/class/net/eth0/statistics/tx_bytes)
NETWORK_RX=$(cat /sys/class/net/eth0/statistics/rx_bytes)

# System Uptime
UPTIME=$(uptime -p)

echo "Instance ID: $INSTANCE_ID"
echo "Availability Zone: $AZ"
echo "Instance Type: $INSTANCE_TYPE"
echo "Memory Utilisation: $MEMORYUSAGE"
echo "CPU Load Average (1, 5, 15 min): $CPU_LOAD"
echo "Disk Usage on /: $DISK_USAGE"
echo "Number of Processes: $PROCESSES"
if [ $HTTPD_PROCESSES -ge 1 ]; then
    echo "Web server is running"
else
    echo "Web server is NOT running"
fi
echo "Network Usage - Transfered: $NETWORK_TX bytes, Received: $NETWORK_RX bytes"
echo "System Uptime: $UPTIME"
