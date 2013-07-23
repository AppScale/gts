<?php
/**
 * Copyright 2007 Google Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
namespace google\net;

require_once 'google/appengine/runtime/proto/ProtocolBufferDecodeError.php';

/**
 * Class to decode protocol buffer from serialized form. Used by protocol
 * buffer implementation.
 */
class Decoder {
  const NUMERIC     = 0;
  const DOUBLE      = 1;
  const STRING      = 2;
  const STARTGROUP  = 3;
  const ENDGROUP    = 4;
  const FLOAT       = 5;
  const MAX_TYPE    = 6;

  const MAX_SHIFT = "1180591620717411303424";  // bcpow(128, 10)
  const MAX_INT64 = "9223372036854775807";     // bcsub(bcpow(2, 63), 1)
  const MIN_INT64 = "-9223372036854775808";    // bcsub(0, bcpow(2, 63))
  const MAX_INT32 = "2147483647";              // bcsub(bcpow(2, 31), 1)
  const MIN_INT32 = "-2147483648";             // bcsub(0,bcpow(2, 31))
  const RANGE_UINT64 = "18446744073709551616"; // bcpow(2, 64)
  const RANGE_UINT32 = "4294967296";           // bcpow(2, 32)

  private $buf;
  private $idx;
  private $limit;

  public function __construct($buf, $idx, $limit) {
    $this->buf = $buf;
    $this->idx = $idx;
    $this->limit = $limit;
  }

  public function avail() {
    return $this->limit - $this->idx;
  }

  public function buffer() {
    return $this->buf;
  }

  public function pos() {
    return $this->idx;
  }

  public function skip($n) {
    if ($this->idx + $n > $this->limit) {
      throw new ProtocolBufferDecodeError("truncated");
    }
    $this->idx += $n;
  }

  public function skipData($tag) {
    $t = $tag & 7;  // tag format type
    if ($t == Decoder::NUMERIC) {
      # TODO: use faster version of getVarInt64 which doesn't return
      # value skipVarInt64?
      $this->getVarInt64();
    } elseif ($t == Decoder::DOUBLE) {
      $this->skip(8);
    } elseif ($t == Decoder::STRING) {
      $n = $this->getVarInt32();
      if ($n < 0) {
        throw new ProtocolBufferDecodeError("corrupted");
      }
      $this->skip($n);
    } elseif ($t == Decoder::STARTGROUP) {
      while (1) {
        $t = $this->getVarInt32();
        if (($t & 7) == Decoder::ENDGROUP) {
          break;
        } else {
          $this->skipData($t);
        }
      }
      if (($t - Decoder::ENDGROUP) != ($tag - Decoder::STARTGROUP)) {
        throw new ProtocolBufferDecodeError("corrupted");
      }
    } elseif ($t == Decoder::ENDGROUP) {
      throw new ProtocolBufferDecodeError("corrupted");
    } elseif ($t == Decoder::FLOAT) {
      $this->skip(4);
    } else {
      throw new ProtocolBufferDecodeError("corrupted");
    }
  }

  // these are all unsigned gets
  public function get8() {
    if ($this->idx >= $this->limit) {
      throw new ProtocolBufferDecodeError("truncated");
    }
    $c = unpack("C*", substr($this->buf, $this->idx, 1));
    $this->idx += 1;
    return $c[1];
  }

  public function getVarUint32() {
    $b = $this->get8();
    if (($b & 128) == 0) {
      return $b;
    }

    $result = $b & 127;
    $mul = 128;

    // Loop for values within sint32 range:
    for ($i = 1; $i < 4; $i++) {
      $b = $this->get8();
      $result += $mul * ($b & 127);

      if (($b & 128) == 0) {
        return $result;
      }
      $mul *= 128;
    }

    // Handing uint32 which may be outside of sint32 range:
    $b = $this->get8();

    if (($b & 128) != 0) {
      throw new ProtocolBufferDecodeError("corrupted");
    }

    $result = bcadd($result, bcmul($b & 127, $mul));

    if (bccomp($result, Decoder::MAX_INT32) <= 0) {
      return intval($result);
    }

    if (bccomp($result, Decoder::RANGE_UINT32) >= 0) {
      throw new ProtocolBufferDecodeError("corrupted");
    }

    return $result;
  }

  public function getVarInt32() {
    $b = $this->get8();
    if (($b & 128) == 0) {
      return $b;
    }

    $result = $b & 127;
    $mul = 128;

    // Loop for values within sint32 range:
    for ($i = 1; $i < 4; $i++) {
      $b = $this->get8();
      $result += $mul * ($b & 127);

      if (($b & 128) == 0) {
        return $result;
      }
      $mul *= 128;
    }

    // Switch to big integer math outside of sint32 range:
    while (1) {
      $b = $this->get8();
      $result = bcadd($result, bcmul($b & 127, $mul));
      $mul = bcmul($mul, 128);

      if (($b & 128) == 0) {
        if (bccomp($result, Decoder::RANGE_UINT64) >= 0) {
          throw new ProtocolBufferDecodeError("corrupted");
        }
        break;
      }
      if (bccomp($mul, Decoder::MAX_SHIFT) > 0) {
        throw new ProtocolBufferDecodeError("corrupted");
      }
    }

    if (bccomp($result, Decoder::MAX_INT64) > 0) {
      $result = bcsub($result, Decoder::RANGE_UINT64);
    }
    if (bccomp($result, Decoder::MAX_INT32) > 0
      || bccomp($result, Decoder::MIN_INT32) < 0) {
      throw new ProtocolBufferDecodeError("corrupted");
    }
    return intval($result);
  }

  public function getVarInt64() {
    $result = $this->getVarUint64();
    if (bccomp($result, Decoder::MAX_INT64) > 0) {
      $result = bcsub($result, Decoder::RANGE_UINT64);
    }
    return $result;
  }

  public function getVarUint64() {
    $result = 0;
    $mul = 1;

    while (1) {
      if (bccomp($mul, Decoder::MAX_SHIFT) > 0) {
        throw new ProtocolBufferDecodeError("corrupted");
      }
      $b = $this->get8();
      $result = bcadd($result, bcmul($b & 127, $mul));
      $mul = bcmul($mul, 128);

      if (($b & 128) == 0) {
        if (bccomp($result, Decoder::RANGE_UINT64) >= 0) {
          throw new ProtocolBufferDecodeError("corrupted");
        }
        return $result;
      }
    }
  }

  public function getBoolean() {
    $b = $this->get8();
    if ($b != 0 && $b != 1) {
      throw new ProtocolBufferDecodeError("corrupted");
    }
    return $b == 1;
  }

  public function getFloat() {
    if ($this->idx + 4 > $this->limit) {
      throw new ProtocolBufferDecodeError("truncated");
    }
    $sub = substr($this->buf, $this->idx, 4);
    $this->idx += 4;
    $res = unpack('f1', $sub);
    return $res[1];
  }

  public function getDouble() {
    if ($this->idx + 8 > $this->limit) {
      throw new ProtocolBufferDecodeError("truncated");
    }
    $sub = substr($this->buf, $this->idx, 8);
    $this->idx += 8;
    $res = unpack('d1', $sub);
    return $res[1];
  }

  public function getFixed32() {
    if ($this->idx + 4 > $this->limit) {
      throw new ProtocolBufferDecodeError("truncated");
    }
    $sub = substr($this->buf, $this->idx, 4);
    $this->idx += 4;
    $res = unpack('V1', $sub);
    $val = $res[1];

    if ($val < 0) {
      $val = bcadd(Decoder::RANGE_UINT32, $val);
    }
    return $val;
  }

  public function getFixed64() {
    $l = $this->getFixed32();
    $h = $this->getFixed32();
    $res = bcadd(bcmul($h, Decoder::RANGE_UINT32), $l);
    return $res;
  }
}
