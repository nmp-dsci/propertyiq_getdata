
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SelectField,\
    SubmitField
from wtforms.validators import Required, Length, Email, Regexp
from wtforms import ValidationError


class SuburbProfile(FlaskForm):
    location = StringField('Location?', validators=[Required()])
    submit = SubmitField('Submit')
