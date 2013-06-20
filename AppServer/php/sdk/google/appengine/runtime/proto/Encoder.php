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

require_once 'google/appengine/runtime/proto/Decoder.php';
require_once 'google/appengine/runtime/proto/ProtocolBufferEncodeError.php';

/**
 * Class to encode protocol buffer into serialized form. Used by protocol
 * buffer implementation.
 */
class Encoder {
  private $buf = "";

  private function putVarInt32Internal($val) {
    if ($val < 0) {
      for ($i = 0; $i < 9; $i++) {
        $this->buf .= pack('C1', ($val & 127) | 128);
        $val >>= 7;
      }
      $this->buf .= pack('C1', 1);
    } else {
      while ($val != 0) {
        $bits = $val & 127;
        $val >>= 7;
        if ($val != 0) {
          $bits |= 128;
        }

        $this->buf .= pack('C1', $bits);
      }
    }
  }

  public function putVarInt32($val) {
    if (($val & 127) == $val) {
      $this->buf .= pack('C1', $val);
      return;
    }

    // Cheaper approximate check, then more expensive precise check.
    // On ia32 we cannot distinguish MAX_INT32 and values larges than
    // MAX_INT32 without bcmath.
    if ($val >= Decoder::MAX_INT32 && bccomp($val, Decoder::MAX_INT32) > 0) {
      throw new ProtocolBufferEncodeError(
        "Value out of sint32 range: " . $val);
    }

    // Similar check for negative numbers.
    if ($val <= Decoder::MIN_INT32 && bccomp($val, Decoder::MIN_INT32) < 0) {
      throw new ProtocolBufferEncodeError(
        "Value out of sint32 range: " . $val);
    }

    $this->putVarInt32Internal($val);
  }

  public function putVarUint64Internal($val) {
    while (bccomp($val, 0) != 0) {
      $bits = bcmod($val, 128);
      $val = bcdiv($val, 128);
      if (bccomp($val, 0) != 0) {
        $bits |= 128;
      }

      $this->buf .= pack('C1', $bits);
    }
  }

  public function putVarUint32($val) {
    if (($val & 127) == $val) {
      $this->buf .= pack('C1', $val);
      return;
    }

    if ($val < 0) {
      throw new ProtocolBufferEncodeError(
        "Value out of uint32 range: " . $val);
    }

    if ($val < Decoder::MAX_INT32) {
      $this->putVarInt32Internal($val);
      return;
    }

    if (bccomp($val, Decoder::RANGE_UINT32) >= 0) {
      throw new ProtocolBufferEncodeError(
        "Value out of uint32 range: " . $val);
    }

    $this->putVarUint64Internal($val);
  }

  public function putVarUint64($val) {
    if ($val < 0) {
      throw new ProtocolBufferEncodeError(
        "Value out of uint64 range: " . $val);
    }
    if ($val < Decoder::MAX_INT32) {
      $this->putVarInt32($val);
      return;
    }
    if (bccomp($val, Decoder::RANGE_UINT64) >= 0) {
      throw new ProtocolBufferEncodeError(
        "Value out of uint64 range: " . $val);
    }

    $this->putVarUint64Internal($val);
  }

  public function putVarInt64($val) {
    if (bccomp($val, 0) >= 0) {
      if (bccomp($val, Decoder::MAX_INT64) > 0) {
        throw new ProtocolBufferEncodeError(
          "Value out of sint64 range: " . $val);
      }
    } else {
      if (bccomp($val, Decoder::MIN_INT64) < 0) {
        throw new ProtocolBufferEncodeError(
          "Value out of sint64 range: " . $val);
      }
      $val = bcadd($val, Decoder::RANGE_UINT64);
    }
    $this->putVarUint64($val);
  }

  public function putBoolean($val) {
    if ($val === true) {
      $this->putVarInt32(1);
    } elseif ($val === false) {
      $this->putVarInt32(0);
    } else {
      throw new ProtocolBufferEncodeError("Bool proto value expected");
    }
  }

  public function put32($val) {
    if ($val < 0) {
      throw new ProtocolBufferEncodeError(
        "Value out of fixed32 range: " . $val);
    }
    if ($val >= Decoder::MIN_INT32 && bccomp($val, Decoder::RANGE_UINT32) >= 0) {
      throw new ProtocolBufferEncodeError(
        "Value out of fixed32 range: " . $val);
    }
    if (bccomp($val, Decoder::MAX_INT32) > 0) {
      $val = bcsub($val, Decoder::RANGE_UINT32);
    }
    $this->buf .= pack('V1', $val);
  }

  public function put64($val) {
    if ($val < 0) {
      throw new ProtocolBufferEncodeError(
        "Value out of fixed64 range: " . $val);
    }
    if (bccomp($val, Decoder::RANGE_UINT64) >= 0) {
      throw new ProtocolBufferEncodeError(
        "Value out of fixed64 range: " . $val);
    }
    $this->put32(bcmod($val, Decoder::RANGE_UINT32));
    $this->put32(bcdiv($val, Decoder::RANGE_UINT32));
  }

  public function putFloat($val) {
    // TODO: big endian not supported
    $this->buf .= pack('f1', $val);
  }

  public function putDouble($val) {
    // TODO: big endian not supported
    $this->buf .= pack('d1', $val);
  }

  public function putPrefixedString($out) {
    $this->putVarInt32(strlen($out));
    $this->buf .= $out;
  }

  public function toString() {
    return $this->buf;
  }
}

