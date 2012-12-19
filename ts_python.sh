# Unit test for different components
export MANAGER='AppManager/test/unit'
export LIB='lib/test/unit'
export DB='AppDB/test/unit'

# Add all the directories separated by a space
export DIRS="$LIB $MANAGER $DB"

# Nose will run all the tests in the directories given
nosetests $DIRS
