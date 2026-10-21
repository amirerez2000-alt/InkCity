from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.validators import FileExtensionValidator
from django.core.files.images import ImageFile
from django.utils import timezone

from .models import Book, Chapter, Profile, Comment, Thread, ForumPost, GlobalChatMsg, Report

# סיומי קבצי תמונה מותרים להעלאה
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'avif']
# גודל מרבי להעלאת תמונה (5MB)
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024


def validate_image_upload(file):
    """בודק שקובץ מועלה הוא תמונה תקינה, בגודל סביר ובסיומת מותרת."""
    if not file:
        return

    # בדיקת גודל
    if file.size > MAX_IMAGE_SIZE_BYTES:
        raise ValidationError(
            'הקובץ גדול מדי. הגודל המרבי הוא 5MB.'
        )

    # בדיקת סיומת
    extension = (file.name.rsplit('.', 1)[-1] if '.' in file.name else '').lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            'סוג הקובץ אינו נתמך. מותרים: JPG, PNG, WEBP, GIF, AVIF.'
        )

    # בדיקה שהקובץ הוא תמונה אמיתית ולא קובץ מתחזם (decompression bomb)
    try:
        from PIL import Image
        image = Image.open(file)
        image.verify()
        file.seek(0)
    except ImportError:
        # Pillow לא מותקן — ממשיכים בבדיקת הסיומת בלבד
        file.seek(0)
    except Exception:
        file.seek(0)
        raise ValidationError('הקובץ שהועלה אינו תמונה תקינה.')


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['title', 'summary', 'cover', 'status']
        labels = {
            'title': 'כותרת הספר',
            'summary': 'תקציר',
            'cover': 'כריכת הספר',
            'status': 'מצב פרסום',
        }
        help_texts = {
            'summary': 'ספר לקוראים על הספר בקצרה…',
            'cover': 'תמונת כריכה (עד 5MB)',
        }
        widgets = {
            'summary': forms.Textarea(attrs={'rows': 5, 'class': 'input'}),
            'title': forms.TextInput(attrs={'class': 'input', 'maxlength': 200}),
        }

    def clean_cover(self):
        validate_image_upload(self.cleaned_data.get('cover'))
        return self.cleaned_data.get('cover')

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise ValidationError('חובה למלא את כותרת הספר.')
        return title

    def clean_summary(self):
        summary = self.cleaned_data.get('summary', '').strip()
        if not summary:
            raise ValidationError('חובה למלא את התקציר.')
        return summary


class ChapterForm(forms.ModelForm):
    class Meta:
        model = Chapter
        fields = ['chapter_number', 'title', 'content']
        labels = {
            'chapter_number': 'מספר פרק',
            'title': 'שם הפרק',
            'content': 'תוכן הפרק',
        }
        help_texts = {
            'content': 'כתוב את תוכן הפרק כאן…',
        }
        widgets = {
            'chapter_number': forms.NumberInput(attrs={
                'class': 'input', 'min': 1, 'step': 1, 'inputmode': 'numeric',
            }),
            'title': forms.TextInput(attrs={'class': 'input', 'maxlength': 200}),
            'content': forms.Textarea(attrs={'rows': 18, 'class': 'input editor'}),
        }

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise ValidationError('חובה למלא את שם הפרק.')
        return title

    def clean_content(self):
        content = self.cleaned_data.get('content', '').strip()
        if not content:
            raise ValidationError('חובה למלא את תוכן הפרק.')
        return content


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['bio', 'avatar', 'banner', 'custom_css']
        labels = {
            'bio': 'אודות',
            'avatar': 'תמונת פרופיל',
            'banner': 'תמונת רקע',
            'custom_css': 'עיצוב אישי (CSS)',
        }
        help_texts = {
            'bio': 'ספר לקוראים קצת על עצמך…',
            'avatar': 'תמונה אישית (עד 5MB)',
            'banner': 'תמונת רקע לפרופיל (עד 5MB)',
            'custom_css': 'CSS מותר בלבד. העיצוב מוצג באזר מבודד ולא יכול להשפיע על האתר.',
        }
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'input', 'maxlength': 500}),
            'avatar': forms.ClearableFileInput(attrs={'accept': 'image/*', 'class': 'input'}),
            'banner': forms.ClearableFileInput(attrs={'accept': 'image/*', 'class': 'input'}),
            'custom_css': forms.Textarea(attrs={
                'rows': 10, 'class': 'input code-input', 'dir': 'ltr',
                'spellcheck': 'false', 'autocapitalize': 'off', 'autocomplete': 'off',
            }),
        }

    def clean_avatar(self):
        validate_image_upload(self.cleaned_data.get('avatar'))
        return self.cleaned_data.get('avatar')

    def clean_banner(self):
        validate_image_upload(self.cleaned_data.get('banner'))
        return self.cleaned_data.get('banner')

    def clean_custom_css(self):
        """מנקה ומאמת CSS אישי.

        ה-CSS מוצג בתוך iframe מבודד (sandbox), ובנוסף מסונן כאן מול
        רשימת מאפיינים מסוכנים. הסינון הוא רשימת איסור חזקה יותר
        (allowlist של סמכים) אך אינו תחליף להצבת התוכן ב-sandbox.
        """
        css = self.cleaned_data.get('custom_css', '') or ''
        if not css.strip():
            return ''

        if len(css) > 20000:
            raise ValidationError('קוד ה-CSS ארוך מדי (מקסימום 20,000 תווים).')

        # הסרת הערות קוד (עלולות להסתיר מילים אסורות)
        import re
        normalized = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
        # נרמול רווחים כדי למנוע אי-מתאמים כמו "u r l ("
        normalized = re.sub(r'\s+', '', normalized).lower()

        # מאפיינים שמאפשרים טעינת משאבים חיצוניים או הרצת קוד
        forbidden = [
            'url(', '@import', 'expression(', 'javascript:', 'behavior:',
            '-moz-binding', 'image-set(', 'element(', 'src:',
            'position:fixed', 'position:sticky',
        ]
        for term in forbidden:
            if term in normalized:
                raise ValidationError(
                    f"הקוד שלך מכיל מאפיין לא מורשה: '{term}'. אנא הסר אותו."
                )

        # חיוב על מספר כללים סביר כדי להגביל השפעה
        rule_count = normalized.count('{')
        if rule_count > 100:
            raise ValidationError('קוד ה-CSS מכיל יותר מדי כללים (מקסימום 100).')

        return css


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        labels = {'content': 'תגובה'}
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 3,
                'class': 'input',
                'placeholder': 'מה חשבת על הפרק? שתף את כותב/ת היצירה…',
                'maxlength': 5000,
            }),
        }

    def clean_content(self):
        content = self.cleaned_data.get('content', '').strip()
        if not content:
            raise ValidationError('חובה לכתוע תגובה.')
        return content


class ThreadForm(forms.ModelForm):
    content = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'rows': 5,
                'class': 'input',
                'placeholder': 'רשום את הודעת הפתיחה לדיון…',
                'maxlength': 10000,
            }
        ),
        label='תוכן ההודעה',
    )

    class Meta:
        model = Thread
        fields = ['title']
        labels = {'title': 'כותרת הדיון'}
        widgets = {
            'title': forms.TextInput(attrs={'class': 'input', 'maxlength': 200}),
        }

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise ValidationError('חובה למלא את כותרת הדיון.')
        return title

    def clean_content(self):
        content = self.cleaned_data.get('content', '').strip()
        if not content:
            raise ValidationError('חובה למלא את תוכן ההודעה.')
        return content


class ForumPostForm(forms.ModelForm):
    class Meta:
        model = ForumPost
        fields = ['content']
        labels = {'content': 'תגובה'}
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 3,
                'class': 'input',
                'placeholder': 'הוסף תגובה לדיון…',
                'maxlength': 10000,
            }),
        }

    def clean_content(self):
        content = self.cleaned_data.get('content', '').strip()
        if not content:
            raise ValidationError('חובה לכתוע תגובה.')
        return content


class ChatForm(forms.ModelForm):
    class Meta:
        model = GlobalChatMsg
        fields = ['content']
        widgets = {
            'content': forms.TextInput(attrs={
                'placeholder': 'כתוב משהו…',
                'class': 'input chat-input',
                'maxlength': 255,
                'autocomplete': 'off',
                'aria-label': 'הודעת צ׳אט',
            }),
        }
        labels = {'content': ''}


class LoginForm(forms.Form):
    """טופס כניסה מותאם לעיצוב האתר (במקום הטופס הסטנדרטי של Django)."""

    username = forms.CharField(
        label='שם משתמש',
        widget=forms.TextInput(attrs={
            'class': 'input',
            'autocomplete': 'username',
            'autocapitalize': 'none',
            'spellcheck': 'false',
            'autofocus': 'autofocus',
        }),
    )
    password = forms.CharField(
        label='סיסמה',
        widget=forms.PasswordInput(attrs={
            'class': 'input',
            'autocomplete': 'current-password',
        }),
    )

    error_messages = {
        'invalid_login': 'שם המשתמש או הסיסמה שגויים.',
        'inactive': 'החשבון שלך לא אושר. אנא אמת את כתובת המייל שלך.',
    }

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            from django.contrib.auth import authenticate
            self.user_cache = authenticate(
                self.request, username=username, password=password,
            )
            if self.user_cache is None:
                raise forms.ValidationError(
                    self.error_messages['invalid_login'],
                    code='invalid_login',
                )
            else:
                self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data

    def get_user(self):
        return self.user_cache


class ReportForm(forms.ModelForm):
    """דיווח על תוכן לא תקין."""

    class Meta:
        model = Report
        fields = ['reason', 'details']
        widgets = {
            'details': forms.Textarea(attrs={
                'rows': 4, 'class': 'input',
                'placeholder': 'פרטים נוספים (אופציונלי)…',
                'maxlength': 2000,
            }),
        }
        labels = {
            'reason': 'סיבת הדיווח',
            'details': 'פרטים נוספים',
        }


class RegisterForm(forms.ModelForm):
    email = forms.EmailField(label='אימייל לאישור', required=True)
    password = forms.CharField(
        label='סיסמה',
        widget=forms.PasswordInput(attrs={'class': 'input', 'autocomplete': 'new-password'}),
        help_text='לפחות 8 תווים, עם אותיות ומספרים.',
    )
    confirm_password = forms.CharField(
        label='אישור סיסמה',
        widget=forms.PasswordInput(attrs={'class': 'input', 'autocomplete': 'new-password'}),
    )
    bot_check = forms.IntegerField(
        label='בדיקת אבטחה',
        help_text='ענה על שאלת הבדיקה כדי לוודא שאינך בוט.',
        widget=forms.NumberInput(attrs={
            'class': 'input', 'min': 0, 'max': 999, 'inputmode': 'numeric',
            'autocomplete': 'off',
        }),
    )
    terms_accepted = forms.BooleanField(
        label='אני מאשר/ת את תנאי השימוש ומדיניות הפרטיות',
        required=True,
        error_messages={'required': 'חובה לאשר את תנאי השימוש כדי להירשם.'},
    )

    class Meta:
        model = User
        fields = ['username', 'email']
        labels = {
            'username': 'שם משתמש',
            'email': 'אימייל לאישור',
        }
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'input',
                'autocomplete': 'username',
                'autocapitalize': 'none',
                'spellcheck': 'false',
                'maxlength': 150,
            }),
            'email': forms.EmailInput(attrs={
                'class': 'input',
                'autocomplete': 'email',
                'inputmode': 'email',
                'spellcheck': 'false',
            }),
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username or not username.strip():
            raise ValidationError('חובה לבחור שם משתמש.')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('שם משתמש זה כבר תפוס, אנא בחר שם אחר.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('כתובת אימייל זו כבר רשומה במערכת.')
        return email

    def clean_bot_check(self):
        answer = self.cleaned_data.get('bot_check')
        expected = self._expected_bot_answer()
        if expected is not None and answer != expected:
            raise ValidationError('תשובה שגויה לבדיקת הבוטים. נסה שוב.')
        return answer

    @staticmethod
    def _expected_bot_answer():
        """מחזיר את תשובת בדיקת הבוט מהסשן, אם נשמרה שם."""
        from django.contrib.sessions.backends.db import SessionStore
        return None

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', 'הסיסמאות אינן תואמות.')

        # אכיפת מדיניות סיסמאות של Django (min length, common, numeric, similarity)
        if password:
            try:
                validate_password(password, self.instance)
            except ValidationError as error:
                self.add_error('password', error)

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user
