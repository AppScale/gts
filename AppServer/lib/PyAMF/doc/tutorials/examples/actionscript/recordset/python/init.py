# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Creates the database for the RecordSet example.

@since: 0.1.0
"""

import db

def init_data(engine):
    languages = [
        (".java", "Sun Java programming language", "Java",),
        (".py", "Python programming language", "Python",),
        (".php", "PHP programming language", "PHP",),
    ]
    
    software_info = [
        ("Red5", True, "Red5 is an open source Flash media server with RTMP/AMF/FLV support.", ".java", "http://osflash.org/red5",),
        ("RTMPy", True, "RTMPy is an RTMP protocol for the Twisted framework.", ".py", "http://rtmpy.org",),
        ("SabreAMF", True, "SabreAMF is an AMF library for PHP5.", ".php", "http://osflash.org/sabreamf",),
        ("Django", True, "Django is a high-level Python Web framework.", ".py", "http://djangoproject.com",),
        ("Zend", True, "Zend is an open source PHP framework.", ".php", "http://framework.zend.com",),
    ]

    for language in languages:
        ins = db.language.insert(values=dict(ID=language[0],
            Description=language[1], Name=language[2]))

        engine.execute(ins)

    for software in software_info:
        name, active, details, cat_id, url = software
 
        ins = db.software.insert(values={
            'Name': name, 'Active': active, 'Details': details,
            'CategoryID': cat_id, 'Url': url})

        engine.execute(ins)

def main():
    engine = db.get_engine()

    print "Creating database..."
    db.create(engine)

    init_data(engine)
    print "Successfully set up."

if __name__ == '__main__':
    main()
