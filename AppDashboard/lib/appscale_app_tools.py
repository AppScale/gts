""" Tools to help AppDashboard interact with app. """
import tempfile
import os

class AppScaleAppTools:
  """ Tools to help AppDashboard interact with app. """

  @classmethod
  def upload_app(cls, upload_file):
    """ Uploads and App into AppScale.
    Args:  tgz_file: a 'StringIO' object containing the uploaded file data.
    Returns: a message reporting the success or failure of the upload.
    """
    #TODO
#    tgz_file = tempfile.NamedTemporaryFile()
#    tgz_file.write( upload_file.read() )
#    name = tgz_file.name
#    tgz_file.close()
    return "AppScaleAppTools.upload_app()"

  @classmethod
  def delete_app(cls, app_name):
    #TODO
    return "AppScaleAppTools.delete_app("+app_name+")"
    


