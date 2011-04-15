package com.google.appengine.api.memcache.dev;

import com.google.appengine.repackaged.com.google.common.base.Preconditions;

class LRU<E extends Chainable<E>>
{
  private Chainable<E> newest;
  private Chainable<E> oldest;

  public LRU()
  {
    clear();
  }

  public void clear()
  {
    this.newest = null;
    this.oldest = null;
  }

  public boolean isEmpty()
  {
    return ((getNewest() == null) && (getOldest() == null));
  }

  public Chainable<E> getNewest()
  {
    return this.newest;
  }

  public Chainable<E> getOldest()
  {
    return this.oldest;
  }

  public void update(Chainable<E> element)
  {
    Preconditions.checkNotNull(element);
    remove(element);
    if (this.newest != null) this.newest.setNewer(element);
    element.setNewer(null);
    element.setOlder(this.newest);
    this.newest = element;
    if (this.oldest != null) return; this.oldest = element;
  }

  public void remove(Chainable<E> element)
  {
    Preconditions.checkNotNull(element);
    Chainable<E> newer = (Chainable<E>)element.getNewer();
    Chainable<E> older = (Chainable<E>)element.getOlder();
    if (newer != null) newer.setOlder(older);
    if (older != null) older.setNewer(newer);
    if (element == this.newest) this.newest = older;
    if (element == this.oldest) this.oldest = newer;
    element.setNewer(null);
    element.setOlder(null);
  }

  public  Chainable<E> removeOldest()
  {
    Chainable<E> oldest = getOldest();
    remove(oldest);
    return oldest;
  }

  public static abstract class AbstractChainable<E>
    implements LRU.Chainable<E>
  {
    private Chainable<E> newer;
    private Chainable<E> older;

    public AbstractChainable()
    {
      this.newer = null;
      this.older = null; }

    public Chainable<E> getNewer() { return this.newer; } 
    public Chainable<E> getOlder() { return this.older; } 
    public void setNewer(Chainable<E> newer) { this.newer = newer; } 
    public void setOlder(Chainable<E> older) { this.older = older;
    }
  }

  static abstract interface Chainable<E>
  {
    public abstract Chainable<E> getNewer();

    public abstract Chainable<E> getOlder();

    public abstract void setNewer(Chainable<E> paramE);

    public abstract void setOlder(Chainable<E> paramE);
  }
}