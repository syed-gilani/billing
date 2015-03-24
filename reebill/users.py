import sys
import copy
import pymongo
import bcrypt
import argparse

class User(object):
    '''A class representing a user account. This is a thin wrapper around a
    Mongo document.'''

    def __init__(self, dictionary):
        self.dictionary = dictionary

    @property
    def identifier(self):
        # OpenID URL/Mongo document id: this should be read-only once the
        # account is created
        return self.dictionary['_id']

    @property
    def username(self):
        # we get this from the OpenID identity provider
        return self.dictionary['name']

    @property
    def preferences(self):
        return self.dictionary['preferences']

    @property
    def session_token(self):
        return self.dictionary['session_token']

    @session_token.setter
    def session_token(self, value):
        self.dictionary['session_token'] = value

#    def get_preference(self, key):
#        '''Get a user preference using its name (e.g.
#        "bill_image_resolution").'''
#        return self.dictionary['preferences'][key]
#
#    def set_preference(self, key, value):
#        '''Set (or create) a user preference using its name.'''
#        self.dictionary['preferences'][key] = value

    
class UserDAO:
    '''Data Access Object for reading and writing user data.'''

    # default user account: the one you get when authentication is turned off,
    # and the template for newly-created accounts. this is a class variable
    # because all instances of UserDAO (if there's more than one) should have
    # the same _default_user (otherwise save-prevention would not work)
    default_user = User({
        '_id':'default',
        'name':'Default User',
        'preferences': {
            'bill_image_resolution': 80,
            'difference_threshold': 0.01,
            'default_account_sort_field': 'account',
            'default_account_sort_direction': 'ASC'
        }
    })

    def __init__(self, database, host='localhost', port=27017, **kwargs):
        port = int(port)
        connection = pymongo.Connection(host, port)
        self.collection = connection[database]['users']
    
    def create_user(self, identifier, password, name=None):
        '''Creates a new user with the given identifier and password and saves
        it in the database. The user's human-readable name is 'identifier' by
        default.'''
        if name is None:
            name = identifier

        # make sure this user doesn't already exist:
        if self.user_exists(identifier):
            raise ValueError('A user with identifier "%s" already exists' %
                    identifier)

        # TODO externalize
        # generate a salt, and hash the password + salt
        salt = bcrypt.gensalt()
        pw_hash = bcrypt.hashpw(password, salt)

        # new user is based on default user
        new_user = copy.deepcopy(UserDAO.default_user)
        # TODO 40963069 user property API
        new_user.dictionary['_id'] = identifier
        new_user.dictionary['name'] = name
        new_user.dictionary['password_hash'] = pw_hash
        new_user.dictionary['salt'] = salt

        # save in db
        self.save_user(new_user)

    def user_exists(self, identifier):
        '''Returns True if there is a user with the given identifier (no
        password needed because user's data is not accessed).'''
        return self.collection.find_one({'_id': identifier}) != None

    def load_user(self, identifier, password):
        '''Returns a User object representing the user given by 'identifier' and
        'password'. Returns None if the identifier/password combination was
        wrong.'''
        # get user document from mongo (authentication fails if there isn't one
        # with the given identifier)
        user_dict = self.collection.find_one({
            '_id': identifier,
        })
        if user_dict is None:
            return None

        # hash the given password using the salt from the user document
        pw_hash = bcrypt.hashpw(password, user_dict['salt'])

        # authentication succeeds iff the result matches the password hash
        # stored in the document
        if pw_hash == user_dict['password_hash']:
            return User(user_dict)
        return None

    def load_by_session_token(self, token):
        user_dict = self.collection.find_one({
            'session_token': token,
        })
        if user_dict is None:
            return None

        return User(user_dict)

    def load_openid_user(self, identifier):
        '''Returns a User object representing the user given by 'identifier'
        (username or an OpenID URL), or None if the user is not found.'''
        user_dict = self.collection.find_one({'_id': identifier})
        if user_dict is None:
            return None

        if password != None:
            if 'password' in user_dict:
                if password != user_dict['password']:
                    return None
            else:
                # if password is provided but not needed, ignore it
                pass

        return User(user_dict)

    def save_user(self, user):
        '''Saves the User object 'user' into the database. This overwrites any
        existing user with the same identifier.'''
        # for the default user, do nothing
        if user is UserDAO.default_user:
            return

        self.collection.save(user.dictionary)

    def change_password(self, identifier, old_password, new_password):
        '''Sets a new password for the given user. Returns True for success,
        false for failure.'''
        user = self.load_user(identifier, old_password)
        if user == None:
            return False
        # salt stays the same
        salt = user.dictionary['salt']
        password_hash = bcrypt.hashpw(new_password, salt)
        user.dictionary['password_hash'] = password_hash
        self.save_user(user)
        return True
        
if __name__ == '__main__':
    # command-line arguments
    parser = argparse.ArgumentParser(
            description='Create and authenticate user accounts')
    parser.add_argument('--host', default='localhost',
            help='Database host (default: localhost)')
    parser.add_argument('--db', required=True,
            help='Mongo database containing users')
    parser.add_argument('command', choices=['add', 'check', 'change'],
            help=('"add" to create a user, "check" to test authentication, '
            '"change" to change password'))
    parser.add_argument('identifier')
    parser.add_argument('password')
    parser.add_argument('newpassword', nargs='?') # optional
    args = parser.parse_args()

    dao = UserDAO(**{
        'host': args.host,
        'port': 27017,
        'database': args.db,
        'collection': 'users', # intentionally non-configurable
    })

    if args.command == 'add':
        try:
            dao.create_user(args.identifier, args.password)
        except ValueError:
            print 'User "%s" already exists; use "change" to change password' \
                    % args.identifier
        else:
            print 'New user created'

    elif args.command == 'check':
        result = dao.load_user(args.identifier, args.password)
        if result is None:
            print 'Authentication failed'
        else:
            print 'Authentication succeeded'

    elif args.command == 'change':
        if args.newpassword is None:
            print 'New password must be specified'
            exit(1)
        result = dao.change_password(args.identifier, args.password,
                args.newpassword)
        if result:
            print 'Password changed'
        else:
            print 'Password change failed'