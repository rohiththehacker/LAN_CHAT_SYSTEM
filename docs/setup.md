# Installation & Execution Guide

## Prerequisites
- Python 3.8+ installed on server machine.
- Web browser (Chrome, Firefox, Edge, Safari) on end-user devices.
- Devices connected to the same Local Area Network (Wi-Fi or Ethernet).

---

## Running the Application

### 1. Start the TCP Chat Server
Open terminal in project root and run:
```bash
python3 -m server.server
```
*Outputs:*
```
[INFO]: TCP CHAT SERVER STARTED SUCCESSFULLY
[INFO]: Listening on Interface : 0.0.0.0:5555
[INFO]: Local Access           : localhost:5555
[INFO]: LAN Network Access     : 192.168.x.x:5555
```

### 2. Start the Web Dashboard Bridge
Open a second terminal window and run:
```bash
python3 -m web_bridge.bridge
```
*Outputs:*
```
[INFO]: WEB DASHBOARD BRIDGE STARTED
[INFO]: Local Browser Access : http://localhost:8080
[INFO]: LAN Network Access   : http://192.168.x.x:8080
```

---

## Connecting Devices

### Option A: From Server Machine (Localhost)
Open web browser and navigate to:
```
http://localhost:8080
```

### Option B: From Remote LAN Devices (Laptops, Phones, Tablets)
1. Ensure the device is connected to the **same Wi-Fi/LAN** network.
2. Open web browser on the remote device.
3. Enter the Server machine's LAN IP address:
```
http://<SERVER_LAN_IP>:8080
```

---

## ⚠️ Troubleshooting LAN Connection Timeout

If remote devices get a **Connection Timeout** when visiting `http://<LAN_IP>:8080` or connecting to `5555`, check the following:

### 1. Linux Firewall (UFW) blocking incoming ports (Most Common)
Linux distributions often run `ufw` (Uncomplicated Firewall) which blocks incoming traffic on non-standard ports.

Run these commands in your Linux terminal to allow incoming traffic on ports **8080** and **5555**:

```bash
sudo ufw allow 8080/tcp
sudo ufw allow 5555/tcp
sudo ufw reload
```

To verify UFW status:
```bash
sudo ufw status
```

*(If using `firewalld` on Fedora/RHEL: `sudo firewall-cmd --add-port={8080,5555}/tcp --permanent && sudo firewall-cmd --reload`)*

### 2. Campus / College Wi-Fi "AP Isolation"
If you are connected to a **College / Campus Wi-Fi** or enterprise network (e.g. `172.20.x.x`), the network administrator may have enabled **Access Point (AP) Isolation**. AP Isolation prevents Wi-Fi clients from communicating with each other.

**Solution**:
- Turn on a **Mobile Hotspot** on your phone.
- Connect both the server machine and client device to the mobile hotspot network.
- Obtain the new LAN IP and test again.

---

## Running Test Suite
To run all automated unit and integration tests:
```bash
python3 -m unittest discover -s tests
```
