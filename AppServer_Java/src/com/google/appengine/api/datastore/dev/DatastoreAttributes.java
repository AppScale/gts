// Copyright 2010 Google Inc. All Rights Reserved.

package com.google.appengine.api.datastore;

import com.google.appengine.api.appidentity.AppIdentityService;
import com.google.appengine.api.appidentity.AppIdentityService.ParsedAppId;
import com.google.appengine.api.appidentity.AppIdentityServiceFactory;

/**
 * Attributes of a datastore.
 *
 */
public final class DatastoreAttributes {
  /**
   * Indicates the type of datastore being used.
   *
   */
  public enum DatastoreType {
    UNKNOWN,
    MASTER_SLAVE,
    HIGH_REPLICATION,
  }

  private final DatastoreType datastoreType;
  private static final AppIdentityService appIdentityService =
      AppIdentityServiceFactory.getAppIdentityService();

  DatastoreAttributes() {
    this(DatastoreApiHelper.getCurrentAppId());
  }

  DatastoreAttributes(String appId) {
    ParsedAppId identity = appIdentityService.parseFullAppId(appId);
    datastoreType = DatastoreType.HIGH_REPLICATION;
  }

  /**
   * Gets the datastore type.
   *
   * Only guaranteed to return something other than {@link
   * DatastoreType#UNKNOWN} when running in production and querying the current
   * app.
   */
  public DatastoreType getDatastoreType() {
    return datastoreType;
  }
}
