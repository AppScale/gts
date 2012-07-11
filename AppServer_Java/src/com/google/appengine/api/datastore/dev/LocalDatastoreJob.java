package com.google.appengine.api.datastore.dev;

import com.google.appengine.api.datastore.Key;
import com.google.apphosting.api.DatastorePb;

abstract class LocalDatastoreJob
{
  final HighRepJobPolicy jobPolicy;
  final Key entityGroup;
  boolean newJob = true;
  boolean applied = false;

  LocalDatastoreJob(HighRepJobPolicy jobPolicy, Key entityGroup) {
    if (jobPolicy == null) {
      throw new NullPointerException("jobPolicy cannot be null");
    }
    this.jobPolicy = jobPolicy;

    if (entityGroup == null) {
      throw new NullPointerException("entityGroup cannot be null");
    }
    this.entityGroup = entityGroup;
  }

  final TryApplyResult tryApply()
  {
    try
    {
      TryApplyResult localTryApplyResult = null;
      if (this.newJob)
      {
        if (this.jobPolicy.shouldApplyNewJob(this.entityGroup)) {
          localTryApplyResult = new TryApplyResult(true, apply());
          return localTryApplyResult;
        }
      }
      else if (this.jobPolicy.shouldRollForwardExistingJob(this.entityGroup))
      {
        localTryApplyResult = new TryApplyResult(true, apply());
        return localTryApplyResult;
      }
      localTryApplyResult = new TryApplyResult(false, calculateJobCost());
      return localTryApplyResult; 
    } finally { this.newJob = false; } 
  }

  final DatastorePb.Cost apply()
  {
    if (this.applied) {
      throw new IllegalStateException(String.format("Job on entity group %s was already applied.", new Object[] { this.entityGroup }));
    }

    this.applied = true;
    return applyInternal();
  }

  abstract DatastorePb.Cost applyInternal();

  abstract DatastorePb.Cost calculateJobCost();

  static class TryApplyResult
  {
    final boolean applied;
    final DatastorePb.Cost cost;

    TryApplyResult(boolean applied, DatastorePb.Cost cost)
    {
      this.applied = applied;
      this.cost = cost;
    }
  }
}
