// Copyright 2009 Google Inc. All Rights Reserved.

package com.google.appengine.tools.development.agent.runtime;

import com.google.appengine.tools.development.agent.AppEngineDevAgent;
import com.google.appengine.tools.development.agent.impl.Agent;
import com.google.apphosting.utils.clearcast.ClearCast;

import sun.reflect.Reflection;

import java.lang.reflect.AccessibleObject;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Member;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.security.AccessController;
import java.security.PrivilegedAction;
import java.security.PrivilegedActionException;
import java.security.PrivilegedExceptionAction;
import java.util.Set;

/**
 * Provides runtime support for
 * {@link com.google.appengine.tools.development.agent.AppEngineDevAgent AppEngineDevAgent}.
 *
 */
public class Runtime {

  private static Agent agent = ClearCast.cast(AppEngineDevAgent.getAgent(), Agent.class);
  private static Set<String> blackList = agent.getBlackList();

  public static ClassLoader checkParentClassLoader(ClassLoader loader) {
    ClassLoader systemLoader = ClassLoader.getSystemClassLoader();
    return loader != null && loader != systemLoader ? loader : Runtime.class.getClassLoader();
  }

  public static void recordClassLoader(ClassLoader loader) {
    agent.recordAppClassLoader(loader);
  }

  public static void reject(String className) {
  }

  /**
   * This method is only invoked via injected bytecode.
   *
   * @see RuntimeHelper#checkRestricted(boolean, String, String, String) ;
   */
  @SuppressWarnings("unused")
  public static void checkRestricted(boolean violationIsError, String classStr,
      String callingClassStr, String callingClassCodeSource) {

  }

  private static boolean isBlackListed(Class<?> klass) {
    String className = klass.getName().replace('.', '/');
   return false;
  }

  private static Class<?> verifyWhiteListed(Member m) throws IllegalAccessException {
    Class<?> klass = m.getDeclaringClass();
    return klass;
  }

  private static void verifyReadable(Class<?> caller, Field f, Object target)
      throws IllegalAccessException {
    checkAccess(f, target, caller);
    verifyWhiteListed(f);
  }

  private static void verifyWritable(Class<?> caller, Field f, Object target)
      throws IllegalAccessException {
    checkAccess(f, target, caller);
    Class<?> klass = verifyWhiteListed(f);

    if (getClassLoaderPrivileged(klass) == null) {
      if (!Modifier.isPublic(f.getModifiers())) {
        throw new IllegalAccessException("Private fields can not be set on JRE classes.");
      }
    }
  }

  private static ClassLoader getClassLoaderPrivileged(final Class<?> klass) {
    return AccessController.doPrivileged(new PrivilegedAction<ClassLoader>() {
      @Override
      public ClassLoader run() {
        return klass.getClassLoader();
      }
    });
  }

  public static Object invoke(Method method, Object target, Object[] args) throws
      InvocationTargetException, IllegalAccessException {
    checkAccess(method, target, getCallerClassPrivileged(3));
    verifyWhiteListed(method);
    AccessibilityModifier am = new AccessibilityModifier(method);
    try {
      return method.invoke(target, args);
    } finally {
      am.restore();
    }
  }

  private static Object newInstance_(Class<?> callerClass, Constructor<?> cons, Object[] args)
      throws InstantiationException, IllegalAccessException, InvocationTargetException {
    checkAccess(cons, null, callerClass);
    verifyWhiteListed(cons);
    AccessibilityModifier am = new AccessibilityModifier(cons);
    try {
      return cons.newInstance(args);
    } finally {
      am.restore();
    }
  }

  public static Object newInstance(Constructor<?> cons, Object[] args)
      throws InstantiationException, IllegalAccessException, InvocationTargetException {
    return newInstance_(getImmediateCallerClassPrivileged(), cons, args);
  }

  public static Object newInstance(final Class<?> klass) throws InstantiationException,
      IllegalAccessException {
    try {
      Constructor<?> cons = AccessController.doPrivileged(
          new PrivilegedExceptionAction<Constructor<?>>() {
            @Override
            public Constructor<?> run() throws NoSuchMethodException {
              return klass.getDeclaredConstructor();
            }
          });
      return newInstance_(getImmediateCallerClassPrivileged(), cons, new Object[0]);
    } catch (PrivilegedActionException e) {
      Throwable t = e.getCause();
      if (t instanceof NoSuchMethodException) {
        throw new InstantiationException(t.getMessage());
      }
      throw new RuntimeException(t);
    } catch (InvocationTargetException e) {
      throwAsUnchecked(e.getCause());
      throw new InstantiationException((e.getCause().getMessage()));
    }
  }

  public static Object get(final Field f, final Object obj)
      throws IllegalAccessException, IllegalArgumentException {
    return verifyAndRun(f, obj, Op.Get, new Action<Object>() {
      @Override
      public Object run(Field f, Object target) throws IllegalAccessException {
        return f.get(target);
      }
    });
  }

  public static boolean getBoolean(final Field f, final Object obj)
      throws IllegalAccessException, IllegalArgumentException {
    return verifyAndRun(f, obj, Op.Get, new Action<Boolean>() {
      @Override
      public Boolean run(Field f, Object target) throws IllegalAccessException {
        return f.getBoolean(target);
      }
    });
  }

  public static byte getByte(final Field f, final Object obj)
      throws IllegalAccessException, IllegalArgumentException {
    return verifyAndRun(f, obj, Op.Get, new Action<Byte>() {
      @Override
      public Byte run(Field f, Object target) throws IllegalAccessException {
        return f.getByte(target);
      }
    });
  }

  public static char getChar(final Field f, final Object obj)
      throws IllegalAccessException, IllegalArgumentException {
    return verifyAndRun(f, obj, Op.Get, new Action<Character>() {
      @Override
      public Character run(Field f, Object target) throws IllegalAccessException {
        return f.getChar(target);
      }
    });
  }

  public static double getDouble(final Field f, final Object obj)
      throws IllegalAccessException, IllegalArgumentException {
    return verifyAndRun(f, obj, Op.Get, new Action<Double>() {
      @Override
      public Double run(Field f, Object target) throws IllegalAccessException {
        return f.getDouble(target);
      }
    });
  }

  public static float getFloat(final Field f, final Object obj)
      throws IllegalAccessException, IllegalArgumentException {
    return verifyAndRun(f, obj, Op.Get, new Action<Float>() {
      @Override
      public Float run(Field f, Object target) throws IllegalAccessException {
        return f.getFloat(target);
      }
    });
  }

  public static int getInt(final Field f, final Object obj)
      throws IllegalAccessException, IllegalArgumentException {
    return verifyAndRun(f, obj, Op.Get, new Action<Integer>() {
      @Override
      public Integer run(Field f, Object target) throws IllegalAccessException {
        return f.getInt(target);
      }
    });
  }

  public static long getLong(final Field f, final Object obj)
      throws IllegalAccessException, IllegalArgumentException {
    return verifyAndRun(f, obj, Op.Get, new Action<Long>() {
      @Override
      public Long run(Field f, Object target) throws IllegalAccessException {
        return f.getLong(target);
      }
    });
  }

  public static short getShort(final Field f, final Object obj)
      throws IllegalAccessException, IllegalArgumentException {
    return verifyAndRun(f, obj, Op.Get, new Action<Short>() {
      @Override
      public Short run(Field f, Object target) throws IllegalAccessException {
        return f.getShort(target);
      }
    });
  }

  public static void set(Field f, Object obj, final Object value)
      throws IllegalAccessException, IllegalArgumentException {
    verifyAndRun(f, obj, Op.Set, new Action<Object>() {
      @Override
      public Object run(Field f, Object target) throws IllegalAccessException {
        f.set(target, value);
        return null;
      }
    });
  }

  public static void setBoolean(Field f, Object obj, final boolean value)
      throws IllegalAccessException, IllegalArgumentException {
    verifyAndRun(f, obj, Op.Set, new Action<Object>() {
      @Override
      public Object run(Field f, Object target) throws IllegalAccessException {
        f.setBoolean(target, value);
        return null;
      }
    });
  }

  public static void setByte(Field f, Object obj, final byte value)
      throws IllegalAccessException, IllegalArgumentException {
    verifyAndRun(f, obj, Op.Set, new Action<Object>() {
      @Override
      public Object run(Field f, Object target) throws IllegalAccessException {
        f.setByte(target, value);
        return null;
      }
    });
  }

  public static void setChar(Field f, Object obj, final char value)
      throws IllegalAccessException, IllegalArgumentException {
    verifyAndRun(f, obj, Op.Set, new Action<Object>() {
      @Override
      public Object run(Field f, Object target) throws IllegalAccessException {
        f.setChar(target, value);
        return null;
      }
    });
  }

  public static void setDouble(Field f, Object obj, final double value)
      throws IllegalAccessException, IllegalArgumentException {
    verifyAndRun(f, obj, Op.Set, new Action<Object>() {
      @Override
      public Object run(Field f, Object target) throws IllegalAccessException {
        f.setDouble(target, value);
        return null;
      }
    });
  }

  public static void setFloat(Field f, Object obj, final float value)
      throws IllegalAccessException, IllegalArgumentException {
    verifyAndRun(f, obj, Op.Set, new Action<Object>() {
      @Override
      public Object run(Field f, Object target) throws IllegalAccessException {
        f.setFloat(target, value);
        return null;
      }
    });
  }

  public static void setInt(Field f, Object obj, final int value)
      throws IllegalAccessException, IllegalArgumentException {
    verifyAndRun(f, obj, Op.Set, new Action<Object>() {
      @Override
      public Object run(Field f, Object target) throws IllegalAccessException {
        f.setInt(target, value);
        return null;
      }
    });
  }

  public static void setLong(Field f, Object obj, final long value)
      throws IllegalAccessException, IllegalArgumentException {
    verifyAndRun(f, obj, Op.Set, new Action<Object>() {
      @Override
      public Object run(Field f, Object target) throws IllegalAccessException {
        f.setLong(target, value);
        return null;
      }
    });
  }

  public static void setShort(Field f, Object obj, final short value)
      throws IllegalAccessException, IllegalArgumentException {
    verifyAndRun(f, obj, Op.Set, new Action<Object>() {
      @Override
      public Object run(Field f, Object target) throws IllegalAccessException {
        f.setShort(target, value);
        return null;
      }
    });
  }

  enum Op {
    Get,
    Set
  }

  private interface Action<T> {
    public T run(Field f, Object target) throws IllegalAccessException;
  }

  private static <T> T verifyAndRun(Field f, Object target, Op op, Action<T> action)
      throws IllegalAccessException {
    Class<?> userCaller = getCallerClassPrivileged(3);
    if (op == Op.Get) {
      verifyReadable(userCaller, f, target);
    } else {
      verifyWritable(userCaller, f, target);
    }

    AccessibilityModifier am = new AccessibilityModifier(f);
    try {
      return action.run(f, target);
    } finally {
      am.restore();
    }
  }

  private static boolean isWhiteListed(Class<?> klass, Member member) {
    if (klass == null) {
      return false;
    }

    if (isWhiteListed_(klass, member)) {
      return true;
    }

    if (member instanceof Constructor) {
      return false;
    }

    Class<?>[] interfaces = klass.getInterfaces();

    for (Class<?> i : interfaces) {
      if (isWhiteListed(i, member)) {
        return true;
      }
    }

    Class<?> parentClass = klass.getSuperclass();
    return isWhiteListed(parentClass, member);
  }

  private static boolean isWhiteListed_(Class<?> klass, Member member) {
    if (isBlackListed(klass)) {
      return false;
    }
    if (klass == member.getDeclaringClass()) {
      return true;
    }
    return hasMember(klass, member);
  }

  private static boolean hasMember(Class<?> klass, Member member) {
    if (member instanceof Method) {
      Method m = (Method) member;
      try {
        klass.getDeclaredMethod(m.getName(), m.getParameterTypes());
        return true;
      } catch (NoSuchMethodException e) {
        return false;
      }
    }

    if (member instanceof Constructor) {
      Constructor<?> constructor = (Constructor<?>) member;
      try {
        klass.getDeclaredConstructor(constructor.getParameterTypes());
        return true;
      } catch (NoSuchMethodException e) {
        return false;
      }
    }

    Field field = (Field) member;
    try {
      klass.getDeclaredField(field.getName());
      return true;
    } catch (NoSuchFieldException e) {
      return false;
    }
  }

  private static Class<?> getImmediateCallerClassPrivileged() {
    return getCallerClassPrivileged(3);
  }

  private static Class<?> getCallerClassPrivileged(final int depth) {
    return AccessController.doPrivileged(new PrivilegedAction<Class<?>>() {
      @Override
      public Class<?> run() {
        return Reflection.getCallerClass(depth + 4);
      }
    });
  }

  private static <T extends AccessibleObject & Member> void checkAccess(final T m,
      final Object target, Class<?> caller)
      throws IllegalAccessException {
    if (m.isAccessible()) {
      return;
    }
    checkAccess(caller, m.getDeclaringClass(), target, m.getModifiers());
  }

  private static void checkAccess(final Class<?> caller, final Class<?> member, final Object target,
      final int modifiers) throws IllegalAccessException {
 
  }

  public static void throwAsUnchecked(Throwable t) {
    Runtime.<RuntimeException>throwException_(t);
  }

  @SuppressWarnings("unchecked")
  private static <T extends Throwable> void throwException_(Throwable t) throws T {
    throw (T) t;
  }

  static class AccessibilityModifier {
    private final AccessibleObject obj;
    private final boolean originalAccessibility;

    AccessibilityModifier(AccessibleObject obj) {
      this.obj = obj;
      originalAccessibility = obj.isAccessible();
      setAccessible_(true);
    }

    public void restore() {
      setAccessible_(originalAccessibility);
    }

    private void setAccessible_(final boolean flag) {
      AccessController.doPrivileged(new PrivilegedAction<Object>() {
        @Override
        public Object run() {
          obj.setAccessible(flag);
          return null;
        }
      });
    }
  }
}
