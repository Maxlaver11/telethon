import os
import struct
import time
from typing import List, Optional, Tuple, Union

from ...crypto import AuthKey, decrypt_data_v2, encrypt_data_v2
from ...tl.mtproto.abcs import BadMsgNotification as AbcBadMsgNotification
from ...tl.mtproto.abcs import DestroySessionRes
from ...tl.mtproto.abcs import MsgDetailedInfo as AbcMsgDetailedInfo
from ...tl.mtproto.functions import get_future_salts
from ...tl.mtproto.types import (
    BadMsgNotification,
    BadServerSalt,
    DestroySessionNone,
    DestroySessionOk,
    FutureSalt,
    FutureSalts,
    GzipPacked,
    HttpWait,
    Message,
    MsgContainer,
    MsgDetailedInfo,
    MsgNewDetailedInfo,
    MsgResendReq,
    MsgsAck,
    MsgsAllInfo,
    MsgsStateInfo,
    MsgsStateReq,
    NewSessionCreated,
    Pong,
    RpcAnswerDropped,
    RpcAnswerDroppedRunning,
    RpcAnswerUnknown,
)
from ...tl.mtproto.types import RpcError as GeneratedRpcError
from ...tl.mtproto.types import RpcResult
from ...tl.types import (
    Updates,
    UpdatesCombined,
    UpdateShort,
    UpdateShortChatMessage,
    UpdateShortMessage,
    UpdateShortSentMessage,
    UpdatesTooLong,
)
from ..utils import (
    CONTAINER_MAX_LENGTH,
    CONTAINER_MAX_SIZE,
    DEFAULT_COMPRESSION_THRESHOLD,
    MESSAGE_SIZE_OVERHEAD,
    check_message_buffer,
    gzip_compress,
    gzip_decompress,
    message_requires_ack,
)
from .types import Deserialization, MsgId, Mtp, RpcError

NUM_FUTURE_SALTS = 64

SALT_USE_DELAY = 60

UPDATE_IDS = {
    Updates.constructor_id(),
    UpdatesCombined.constructor_id(),
    UpdateShort.constructor_id(),
    UpdateShortChatMessage.constructor_id(),
    UpdateShortMessage.constructor_id(),
    UpdateShortSentMessage.constructor_id(),
    UpdatesTooLong.constructor_id(),
}

HEADER_LEN = 8 + 8  # salt, client_id

CONTAINER_HEADER_LEN = (8 + 4 + 4) + (4 + 4)  # msg_id, seq_no, size, constructor, len


class Encrypted(Mtp):
    def __init__(
        self,
        auth_key: AuthKey,
        *,
        time_offset: Optional[int] = None,
        first_salt: Optional[int] = None,
        compression_threshold: Optional[int] = DEFAULT_COMPRESSION_THRESHOLD,
    ) -> None:
        self._auth_key = auth_key
        self._time_offset: int = time_offset or 0
        self._salts: List[FutureSalt] = [
            FutureSalt(valid_since=0, valid_until=0x7FFFFFFF, salt=first_salt or 0)
        ]
        self._start_salt_time: Optional[Tuple[int, int]] = None
        self._client_id: int = struct.unpack("<q", os.urandom(8))[0]
        self._sequence: int = 0
        self._last_msg_id: int = 0
        self._pending_ack: List[int] = []
        self._compression_threshold = compression_threshold
        self._rpc_results: List[Tuple[MsgId, Union[bytes, ValueError]]] = []
        self._updates: List[bytes] = []
        self._buffer = bytearray()
        self._msg_count: int = 0

        self._handlers = {
            RpcResult.constructor_id(): self._handle_rpc_result,
            MsgsAck.constructor_id(): self._handle_ack,
            BadMsgNotification.constructor_id(): self._handle_bad_notification,
            BadServerSalt.constructor_id(): self._handle_bad_notification,
            MsgsStateReq.constructor_id(): self._handle_state_req,
            MsgsStateInfo.constructor_id(): self._handle_state_info,
            MsgsAllInfo.constructor_id(): self._handle_msg_all,
            MsgDetailedInfo.constructor_id(): self._handle_detailed_info,
            MsgNewDetailedInfo.constructor_id(): self._handle_detailed_info,
            MsgResendReq.constructor_id(): self._handle_msg_resend,
            FutureSalt.constructor_id(): self._handle_future_salt,
            FutureSalts.constructor_id(): self._handle_future_salts,
            Pong.constructor_id(): self._handle_pong,
            DestroySessionOk.constructor_id(): self._handle_destroy_session,
            DestroySessionNone.constructor_id(): self._handle_destroy_session,
            NewSessionCreated.constructor_id(): self._handle_new_session_created,
            GzipPacked.constructor_id(): self._handle_gzip_packed,
            HttpWait.constructor_id(): self._handle_http_wait,
        }

    @property
    def auth_key(self) -> bytes:
        return self._auth_key.data

    def _correct_time_offset(self, msg_id: int) -> None:
        now = time.time()
        correct = msg_id >> 32
        self._time_offset = correct - int(now)

    def _get_new_msg_id(self) -> int:
        now = time.time()

        new_msg_id = int((now + self._time_offset) * 0x100000000)
        if self._last_msg_id >= new_msg_id:
            new_msg_id = self._last_msg_id + 4

        self._last_msg_id = new_msg_id
        return new_msg_id

    def _get_seq_no(self, content_related: bool) -> int:
        if content_related:
            self._sequence += 2
            return self._sequence - 1
        else:
            return self._sequence

    def _serialize_msg(self, body: bytes, content_related: bool) -> MsgId:
        msg_id = self._get_new_msg_id()
        seq_no = self._get_seq_no(content_related)
        self._buffer += struct.pack("<qii", msg_id, seq_no, len(body))
        self._buffer += body
        self._msg_count += 1
        return MsgId(msg_id)

    def _finalize_plain(self) -> bytes:
        if not self._msg_count:
            return b""

        if self._msg_count == 1:
            del self._buffer[:CONTAINER_HEADER_LEN]

        self._buffer[:HEADER_LEN] = struct.pack(
            "<qq", self._salts[-1].salt if self._salts else 0, self._client_id
        )

        if self._msg_count != 1:
            self._buffer[HEADER_LEN : HEADER_LEN + CONTAINER_HEADER_LEN] = struct.pack(
                "<qiiIi",
                self._get_new_msg_id(),
                self._get_seq_no(False),
                len(self._buffer) - HEADER_LEN - CONTAINER_HEADER_LEN + 8,
                MsgContainer.constructor_id(),
                self._msg_count,
            )

        self._msg_count = 0
        result = bytes(self._buffer)
        self._buffer.clear()
        return result

    def _process_message(self, message: Message) -> None:
        if message_requires_ack(message):
            self._pending_ack.append(message.msg_id)

        # https://core.telegram.org/mtproto/service_messages
        # https://core.telegram.org/mtproto/service_messages_about_messages
        # TODO verify what needs ack and what doesn't
        constructor_id = struct.unpack_from("<I", message.body)[0]
        self._handlers.get(constructor_id, self._handle_update)(message)

    def _handle_rpc_result(self, message: Message) -> None:
        assert isinstance(message.body, RpcResult)
        req_msg_id = message.body.req_msg_id
        result = message.body.result

        msg_id = MsgId(req_msg_id)
        inner_constructor = struct.unpack_from("<I", result)[0]

        if inner_constructor == GeneratedRpcError.constructor_id():
            self._rpc_results.append(
                (
                    msg_id,
                    RpcError.from_mtproto_error(GeneratedRpcError.from_bytes(result)),
                )
            )
        elif inner_constructor == RpcAnswerUnknown.constructor_id():
            pass  # msg_id = rpc_drop_answer.msg_id
        elif inner_constructor == RpcAnswerDroppedRunning.constructor_id():
            pass  # msg_id = rpc_drop_answer.msg_id, original_request.msg_id
        elif inner_constructor == RpcAnswerDropped.constructor_id():
            pass  # dropped
        elif inner_constructor == GzipPacked.constructor_id():
            body = gzip_decompress(GzipPacked.from_bytes(result))
            self._store_own_updates(body)
            self._rpc_results.append((msg_id, body))
        else:
            self._store_own_updates(result)
            self._rpc_results.append((msg_id, result))

    def _store_own_updates(self, body: bytes) -> None:
        constructor_id = struct.unpack_from("I", body)[0]
        if constructor_id in UPDATE_IDS:
            self._updates.append(body)

    def _handle_ack(self, message: Message) -> None:
        # TODO notify about this somehow
        MsgsAck.from_bytes(message.body)

    def _handle_bad_notification(self, message: Message) -> None:
        # TODO notify about this somehow
        bad_msg = AbcBadMsgNotification.from_bytes(message.body)
        if isinstance(bad_msg, BadServerSalt):
            self._rpc_results.append(
                (
                    MsgId(bad_msg.bad_msg_id),
                    ValueError(f"bad msg: {bad_msg.error_code}"),
                )
            )

            self._salts.clear()
            self._salts.append(
                FutureSalt(
                    valid_since=0, valid_until=0x7FFFFFFF, salt=bad_msg.new_server_salt
                )
            )

            self.push(get_future_salts(num=NUM_FUTURE_SALTS))
            return

        assert isinstance(bad_msg, BadMsgNotification)
        self._rpc_results.append(
            (MsgId(bad_msg.bad_msg_id), ValueError(f"bad msg: {bad_msg.error_code}"))
        )

        if bad_msg.error_code in (16, 17):
            self._correct_time_offset(message.msg_id)
        elif bad_msg.error_code == 32:
            # TODO start with a fresh session rather than guessing
            self._sequence += 64
        elif bad_msg.error_code == 33:
            # TODO start with a fresh session rather than guessing
            self._sequence -= 16

    def _handle_state_req(self, message: Message) -> None:
        # TODO implement
        MsgsStateReq.from_bytes(message.body)

    def _handle_state_info(self, message: Message) -> None:
        # TODO implement
        MsgsStateInfo.from_bytes(message.body)

    def _handle_msg_all(self, message: Message) -> None:
        # TODO implement
        MsgsAllInfo.from_bytes(message.body)

    def _handle_detailed_info(self, message: Message) -> None:
        # TODO properly implement
        msg_detailed = AbcMsgDetailedInfo.from_bytes(message.body)
        if isinstance(msg_detailed, MsgDetailedInfo):
            self._pending_ack.append(msg_detailed.answer_msg_id)
        elif isinstance(msg_detailed, MsgNewDetailedInfo):
            self._pending_ack.append(msg_detailed.answer_msg_id)
        else:
            assert False

    def _handle_msg_resend(self, message: Message) -> None:
        # TODO implement
        MsgResendReq.from_bytes(message.body)

    def _handle_future_salts(self, message: Message) -> None:
        # TODO implement
        salts = FutureSalts.from_bytes(message.body)
        self._rpc_results.append((MsgId(salts.req_msg_id), message.body))

        self._start_salt_time = (salts.now, int(time.time()))
        self._salts = salts.salts
        self._salts.sort(key=lambda salt: -salt.valid_since)

    def _handle_future_salt(self, message: Message) -> None:
        FutureSalt.from_bytes(message.body)
        assert False  # no request should cause this

    def _handle_pong(self, message: Message) -> None:
        pong = Pong.from_bytes(message.body)
        self._rpc_results.append((MsgId(pong.msg_id), message.body))

    def _handle_destroy_session(self, message: Message) -> None:
        # TODO implement
        DestroySessionRes.from_bytes(message.body)

    def _handle_new_session_created(self, message: Message) -> None:
        # TODO implement
        new_session = NewSessionCreated.from_bytes(message.body)
        self._salts.clear()
        self._salts.append(
            FutureSalt(
                valid_since=0, valid_until=0x7FFFFFFF, salt=new_session.server_salt
            )
        )

    def _handle_container(self, message: Message) -> None:
        container = MsgContainer.from_bytes(message.body)
        for inner_message in container.messages:
            self._process_message(inner_message)

    def _handle_gzip_packed(self, message: Message) -> None:
        container = GzipPacked.from_bytes(message.body)
        inner_body = gzip_decompress(container)
        self._process_message(
            Message(
                msg_id=message.msg_id,
                seqno=message.seqno,
                bytes=len(inner_body),
                body=inner_body,
            )
        )

    def _handle_http_wait(self, message: Message) -> None:
        # TODO implement
        HttpWait.from_bytes(message.body)

    def _handle_update(self, message: Message) -> None:
        # TODO if this `Updates` cannot be deserialized, `getDifference` should be used
        self._updates.append(message.body)

    def push(self, request: bytes) -> Optional[MsgId]:
        if not self._buffer:
            # Reserve space for `finalize`
            self._buffer += bytes(HEADER_LEN + CONTAINER_HEADER_LEN)

        if self._pending_ack:
            self._serialize_msg(bytes(MsgsAck(msg_ids=self._pending_ack)), False)
            self._pending_ack = []

        if self._start_salt_time:
            start_secs, start_instant = self._start_salt_time
            if len(self._salts) >= 2:
                salt = self._salts[-2]
                now = start_secs + (start_instant - int(time.time()))
                if now >= salt.valid_since + SALT_USE_DELAY:
                    self._salts.pop()
                    if len(self._salts) == 1:
                        self._serialize_msg(
                            bytes(get_future_salts(num=NUM_FUTURE_SALTS)), True
                        )

        if self._msg_count == CONTAINER_MAX_LENGTH:
            return None

        assert len(request) + MESSAGE_SIZE_OVERHEAD <= CONTAINER_MAX_SIZE
        assert len(request) % 4 == 0

        body = request
        if self._compression_threshold is not None:
            if len(request) >= self._compression_threshold:
                compressed = bytes(GzipPacked(packed_data=gzip_compress(request)))
                if len(compressed) < len(request):
                    body = compressed

        new_size = len(self._buffer) + len(body) + MESSAGE_SIZE_OVERHEAD
        if new_size >= CONTAINER_MAX_SIZE:
            return None

        return self._serialize_msg(body, True)

    def finalize(self) -> bytes:
        buffer = self._finalize_plain()
        if not buffer:
            return buffer
        else:
            return encrypt_data_v2(buffer, self._auth_key)

    def deserialize(self, payload: bytes) -> Deserialization:
        check_message_buffer(payload)

        plaintext = decrypt_data_v2(payload, self._auth_key)

        _, client_id = struct.unpack_from("<qq", plaintext)  # salt, client_id
        if client_id != self._client_id:
            raise RuntimeError("wrong session id")

        self._process_message(Message.from_bytes(memoryview(plaintext)[16:]))

        result = Deserialization(rpc_results=self._rpc_results, updates=self._updates)
        self._rpc_results = []
        self._updates = []
        return result