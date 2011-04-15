package com.google.appengine.api.datastore.dev;

import java.io.Serializable;
import java.util.List;

import com.google.storage.onestore.v3.OnestoreEntity;

abstract interface LocalFullTextIndex extends Serializable
{
  public abstract void write(OnestoreEntity.EntityProto paramEntityProto);

  public abstract void delete(OnestoreEntity.Reference paramReference);

  public abstract List<OnestoreEntity.Reference> search(String paramString1, String paramString2);

  public abstract void close();
}