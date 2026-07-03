from . import main
from .. import db
from flask import render_template, redirect, url_for, abort, flash, request,\
    current_app, make_response,session
import json
from .forms import SuburbProfile

@main.route('/',methods=['GET','POST'])
def index():
    form = SuburbProfile()
    if form.validate_on_submit():
        session['location'] = form.location.data
        return redirect(url_for('main.index',form=form,location=session.get('location','Sydney')))
    return render_template('main/index.html',form=form, location=session.get('location','Sydney'))

