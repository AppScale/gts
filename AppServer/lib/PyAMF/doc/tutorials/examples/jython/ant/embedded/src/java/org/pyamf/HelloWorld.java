package org.pyamf;

import org.python.core.PyException;
import org.python.util.PythonInterpreter;

public class HelloWorld
{
    /**
     * @param args the command line arguments
     */
     public static void main(String[] args) throws PyException
     {
        PythonInterpreter interp = new PythonInterpreter();
        interp.execfile("src/python/server.py");
    }
}
