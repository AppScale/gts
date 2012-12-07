public class User
{
    public var name:String;
    public var pass:String;

    public function User(name:String, pass:String)
    {
        this.name = name;
        this.pass = pass
    }
}

public class Permission
{
    public var type:String;

    public function Permission(type:String)
    {
        this.type = type;
    }
}
