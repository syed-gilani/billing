from flask import session, url_for, redirect, request
from flask.ext.admin import AdminIndexView, expose, Admin
from flask.ext.admin.contrib.sqla import ModelView
from core.model import Supplier, Utility, RateClass, UtilityAccount, Session, UtilBill
from brokerage.brokerage_model import BillEntryUser
from reebill.state import ReeBillCustomer, ReeBill


class MyAdminIndexView(AdminIndexView):

    @expose('/')
    def index(self):
        try:
            if session['access_token'] is None:
                return redirect(url_for('login', next=request.url))
            else:
                return super(MyAdminIndexView, self).index()
        except KeyError:
            print request.url
            return redirect(url_for('login', next=request.url))

class CustomModelView(ModelView):
    # Disable create, update and delete on model
    can_create = False
    can_delete = False
    can_edit = False

    def is_accessible(self):
        try:
            if session['access_token'] is None:
                return False
            else:
                return True
        except KeyError:
            return False

    def _handle_view(self, name, **kwargs):
        if not self.is_accessible():
            return redirect(url_for('login', next=request.url))

    def __init__(self, model, session, **kwargs):
        super(CustomModelView, self).__init__(model, session, **kwargs)

class LoginModelView(ModelView):
    def is_accessible(self):
        try:
            if session['access_token'] is None:
                return False
            else:
                return True
        except KeyError:
            return False

    def _handle_view(self, name, **kwargs):
        if not self.is_accessible():
            return redirect(url_for('login', next=request.url))

    def __init__(self, model, session, **kwargs):
        super(LoginModelView, self).__init__(model, session, **kwargs)

class SupplierModelView(LoginModelView):
    form_columns = ('name',)

    def __init__(self, session, **kwargs):
        super(SupplierModelView, self).__init__(Supplier, session, **kwargs)

class UtilityModelView(LoginModelView):
    form_columns = ('name',)

    def __init__(self, session, **kwargs):
        super(UtilityModelView, self).__init__(Utility, session, **kwargs)

class ReeBillCustomerModelView(LoginModelView):
    form_columns = ('name', 'discountrate', 'latechargerate', 'bill_email_recipient', 'service', )

    def __init__(self, session, **kwargs):
        super(ReeBillCustomerModelView, self).__init__(ReeBillCustomer, session, **kwargs)

class RateClassModelView(LoginModelView):

    def __init__(self, session, **kwargs):
        super(RateClassModelView, self).__init__(RateClass, session, **kwargs)

class UserModelView(LoginModelView):
    form_columns = ('email', 'password', )

    def __init__(self, session, **kwargs):
        super(UserModelView, self).__init__(BillEntryUser, session, **kwargs)


def make_admin(app):
    '''Return a new Flask 'Admin' object associated with 'app' representing
    the admin UI.
    '''
    admin = Admin(app, index_view=MyAdminIndexView())
    admin.add_view(CustomModelView(UtilityAccount, Session()))
    admin.add_view(CustomModelView(UtilBill, Session(), name='Utility Bill'))
    admin.add_view(UtilityModelView(Session()))
    admin.add_view(SupplierModelView(Session()))
    admin.add_view(RateClassModelView(Session()))
    admin.add_view(UserModelView(Session()))
    admin.add_view(ReeBillCustomerModelView(Session(), name='ReeBill Account'))
    admin.add_view(CustomModelView(ReeBill, Session(), name='Reebill'))
    return admin
