# Testing Suite & Verification Report

## Test Plan Overview
The system was verified using a combination of **Automated Unit/Integration Tests** (`tests/`) and **Manual LAN Multi-Device Scenarios**.

---

## 1. Automated Test Suite Results

Run command:
```bash
python3 -m unittest discover -s tests
```

### Test Case Execution Log
| Test ID | Test Name | File | Description | Result |
| :--- | :--- | :--- | :--- | :--- |
| **TEST-01** | `test_message_encoders` | `test_protocol.py` | Validates protocol string formatting | **PASS** |
| **TEST-02** | `test_parse_valid_messages` | `test_protocol.py` | Validates command parsing (`JOIN`, `MSG`, `PRIVATE`, `WHO`, `LEAVE`) | **PASS** |
| **TEST-03** | `test_parse_invalid_messages` | `test_protocol.py` | Rejects malformed strings and invalid characters | **PASS** |
| **TEST-04** | `test_stream_buffer_framing` | `test_protocol.py` | Tests TCP framing buffer across partial packet chunks | **PASS** |
| **TEST-05** | `test_single_client_join` | `test_multiclient.py` | Single client socket connection and welcome response | **PASS** |
| **TEST-06** | `test_duplicate_username_rejected` | `test_multiclient.py` | Rejects duplicate username registration over socket | **PASS** |
| **TEST-07** | `test_broadcast_and_private_messaging` | `test_multiclient.py` | Verifies broadcast routing to 3 clients and private PM routing | **PASS** |
| **TEST-08** | `test_abrupt_disconnect` | `test_fault.py` | Closing client socket abruptly without `/quit` does not crash server | **PASS** |
| **TEST-09** | `test_malformed_commands` | `test_fault.py` | Sends garbage string without delimiter; verifies server error response | **PASS** |
| **TEST-10** | `test_command_before_join` | `test_fault.py` | Block commands sent prior to successful registration | **PASS** |
| **TEST-11** | `test_oversized_message` | `test_fault.py` | Rejects messages exceeding maximum allowed byte limit | **PASS** |

**Summary**: **11/11 Automated Tests Passed (100% Success Rate)**.

---

## 2. Manual LAN Multi-Device Test Plan

### Test Scenario A: Localhost Single Machine
1. Start TCP Server: `python3 -m server.server`
2. Start Web Bridge: `python3 -m web_bridge.bridge`
3. Open Browser Window 1 (`http://localhost:8080`), Join as `Alice`.
4. Open Browser Window 2 in Incognito (`http://localhost:8080`), Join as `Bob`.
5. Send broadcast message from Alice -> Bob receives in real-time.
6. Click Bob in Alice's online list -> Send `/pm Bob Secret` -> Delivered only to Bob.

### Test Scenario B: LAN Multi-Device (Same Wi-Fi Network)
1. Find Server Machine's LAN IP (e.g. `192.168.1.15`).
2. On Server Machine, run `python3 -m server.server` and `python3 -m web_bridge.bridge`.
3. Connect Smartphone / Laptop B to the same Wi-Fi network.
4. On Laptop B, open browser: `http://192.168.1.15:8080`.
5. Join as `MobileUser`.
6. Verify bi-directional communication between Server Machine and Laptop B over LAN.
