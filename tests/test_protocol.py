"""
Unit tests for Custom Application Protocol parsing and TCP Stream Buffer framing.
"""

import unittest
from server.protocol import (
    StreamBuffer,
    parse_message,
    ProtocolError,
    encode_join,
    encode_msg,
    encode_private,
    encode_whoreply,
    encode_leave,
    encode_error,
)

class TestProtocol(unittest.TestCase):
    def test_message_encoders(self):
        self.assertEqual(encode_join("alice"), "JOIN:alice\n")
        self.assertEqual(encode_msg("alice", "Hello"), "MSG:alice:Hello\n")
        self.assertEqual(encode_private("alice", "bob", "Secret"), "PRIVATE:alice:bob:Secret\n")
        self.assertEqual(encode_whoreply(["alice", "bob"]), "WHOREPLY:alice,bob\n")
        self.assertEqual(encode_leave("alice"), "LEAVE:alice\n")
        self.assertEqual(encode_error("Invalid user"), "ERROR:Invalid user\n")

    def test_parse_valid_messages(self):
        cmd, args = parse_message("JOIN:alice")
        self.assertEqual(cmd, "JOIN")
        self.assertEqual(args, ["alice"])

        cmd, args = parse_message("MSG:alice:Hello world!")
        self.assertEqual(cmd, "MSG")
        self.assertEqual(args, ["alice", "Hello world!"])

        cmd, args = parse_message("PRIVATE:alice:bob:Top secret message")
        self.assertEqual(cmd, "PRIVATE")
        self.assertEqual(args, ["alice", "bob", "Top secret message"])

        cmd, args = parse_message("WHO")
        self.assertEqual(cmd, "WHO")
        self.assertEqual(args, [])

        cmd, args = parse_message("LEAVE:alice")
        self.assertEqual(cmd, "LEAVE")
        self.assertEqual(args, ["alice"])

    def test_parse_invalid_messages(self):
        with self.assertRaises(ProtocolError):
            parse_message("")

        with self.assertRaises(ProtocolError):
            parse_message("INVALID_COMMAND:foo")

        with self.assertRaises(ProtocolError):
            parse_message("JOIN:")  # Empty username

        with self.assertRaises(ProtocolError):
            parse_message("JOIN:alice:with:colons")  # Invalid character

        with self.assertRaises(ProtocolError):
            parse_message("JOIN:" + "a" * 100)  # Exceeds max length

    def test_stream_buffer_framing(self):
        buffer = StreamBuffer()
        
        # Test case 1: Multiple complete messages in one chunk
        buffer.append("JOIN:alice\nMSG:alice:Hi\n")
        msgs = buffer.extract_messages()
        self.assertEqual(msgs, ["JOIN:alice", "MSG:alice:Hi"])

        # Test case 2: Partial packet across multiple appends
        buffer.append("PRIVATE:alice:b")
        msgs = buffer.extract_messages()
        self.assertEqual(msgs, [])  # Incomplete!

        buffer.append("ob:Hello!\nWHO\n")
        msgs = buffer.extract_messages()
        self.assertEqual(msgs, ["PRIVATE:alice:bob:Hello!", "WHO"])

        # Test case 3: Trailing newline buffer check
        self.assertEqual(buffer.extract_messages(), [])


if __name__ == "__main__":
    unittest.main()
