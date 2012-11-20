package clock;

import java.io.IOException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import com.google.appengine.api.users.User;
import com.google.appengine.api.users.UserService;
import com.google.appengine.api.users.UserServiceFactory;

import clock.UserPrefs;

@SuppressWarnings("serial")
public class PrefsServlet extends HttpServlet {
    public void doPost(HttpServletRequest req,
                       HttpServletResponse resp)
        throws IOException {
        UserService userService = UserServiceFactory.getUserService();
        User user = userService.getCurrentUser();

        UserPrefs userPrefs = UserPrefs.getPrefsForUser(user);

        try {
            int tzOffset = new Integer(req.getParameter("tz_offset")).intValue();
            userPrefs.setTzOffset(tzOffset);
            userPrefs.save();
        } catch (NumberFormatException nfe) {
            // User entered a value that wasn't an integer.  Ignore for now.
        }

        resp.sendRedirect("/");
    }
}
