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
/**
 */

namespace google\appengine\api\app_identity;

/**
 * PublicCertificate contains an X509 public certificate in PEM format and a
 * string which is used to identify this certificate.
 */
final class PublicCertificate {

  /**
   * The name of the certificate.
   * @var string
   */
  private $certificate_name;

  /**
   * The public certificate in X509 PEM format.
   * @var string
   */
  private $certificate;

  /**
   * Creates a new public certificate.
   *
   * @param string $certificate_name The name of the certificate.
   * @param string $certificate_in_pem_format The public certificate in X509
   * PEM format.
   */
  public function __construct($certificate_name,
                              $certificate_in_pem_format) {
    $this->certificate_name = $certificate_name;
    $this->certificate = $certificate_in_pem_format;
  }

  /**
   * Returns the name of this public certificate.
   *
   * @return string The name of the certificate.
   */
  public function getCertificateName() {
    return $this->certificate_name;
  }

  /**
   * Returns the X509 Certificate in PEM format.
   *
   * @return string The public certificate in X509 PEM format.
   */
  public function getX509CertificateInPemFormat() {
    return $this->certificate;
  }
}

