from enum import Enum


class FormScopeType(str, Enum):
    GLOBAL = "global"
    MUNICIPALITY = "municipality"


class FormFieldType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    CHECKBOX = "checkbox"
    DATE = "date"
    WORK_HOLIDAY = "work-holiday"
    SELECT = "select"
    CERTIFICATE_NUMBER = "certificate-number"
    RADIO = "radio"
    TEXT_AREA = "text-area"
    COMPOUND = "compound"
    FLOOR_AREA = "floor-area"


class FormBindingType(str, Enum):
    FIXED = "fixed"
    DYNAMIC = "dynamic"
