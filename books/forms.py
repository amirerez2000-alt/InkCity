from django import forms
from .models import Book, Chapter, Profile, Comment, Thread, ForumPost, GlobalChatMsg
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['title', 'summary', 'cover', 'status'] # הוספנו את הסטטוס
        labels = {
            'status': 'מצב פרסום',
        }

class ChapterForm(forms.ModelForm):
    class Meta:
        model = Chapter
        fields = ['chapter_number', 'title', 'content']

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['bio', 'avatar', 'banner', 'custom_css']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'placeholder': 'ספר לקוראים קצת על עצמך או רשום סטטוס...'}),
            'custom_css': forms.Textarea(attrs={'rows': 10, 'placeholder': 'body { background-color: pink; }...', 'style': 'direction: ltr; text-align: left;'}),
        }

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'מה חשבת על הפרק? שתף את כותב/ת היצירה...',
                'style': 'width: 100%; padding: 10px; box-sizing: border-radius: 4px;'
            }),
        }

class ThreadForm(forms.ModelForm):
  content = forms.CharField(
      widget=forms.Textarea(
          attrs={
              'rows': 5,
              'placeholder': 'רשום את הודעת הפתיחה לדיון...',
          }
      ),
      label='תוכן ההודעה',
  )

  class Meta:
    model = Thread
    fields = ['title']


class ForumPostForm(forms.ModelForm):

  class Meta:
    model = ForumPost
    fields = ['content']
    widgets = {
        'content': forms.Textarea(
            attrs={'rows': 3, 'placeholder': 'הוסף תגובה לדיון...'}
        ),
    }

class ChatForm(forms.ModelForm):
    class Meta:
        model = GlobalChatMsg
        fields = ['content']
        widgets = {
            'content': forms.TextInput(attrs={
                'placeholder': 'כתוב משהו...', 
                'style': 'width: 70%; padding: 8px; border-radius: 4px; border: 1px solid var(--border-color); background: var(--bg-color); color: var(--text-color);'
            }),
        }
        labels = {'content': ''} # להסתיר את המילה "תוכן ההודעה"

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['bio', 'avatar', 'banner', 'custom_css']
        widgets = {
            'custom_css': forms.Textarea(attrs={'rows': 10, 'placeholder': '/* הכנס קוד עיצוב אישי כאן */', 'style': 'direction: ltr; text-align: left;'}),
        }

    def clean_custom_css(self):
        css = self.cleaned_data.get('custom_css', '')
        if not css:
            return css
            
        # רשימה שחורה של מילים מסוכנות
        forbidden_terms = [
            '<', '>',               # חוסם ניסיון לסגור את תגית ה-style ולהכניס סקריפטים (XSS)
            'javascript:', 'expression(', # חוסם הרצת קוד זדוני מתוך CSS
            '@import', 'url(',      # חוסם טעינת קבצים חיצוניים שיכולים לעקוב אחרי גולשים
            'position: fixed', 'position: absolute', # חוסם ניסיון לשים כפתורים בלתי נראים מעל האתר
            'body', 'html', '.navbar' # מונע מהמשתמש להעלים או לשנות את האתר הראשי
        ]
        
        css_lower = css.lower()
        for term in forbidden_terms:
            if term in css_lower:
                raise ValidationError(f"הקוד שלך מכיל תוכן לא מורשה או מסוכן: '{term}'. אנא הסר אותו.")
                
        return css

class RegisterForm(forms.ModelForm):
    email = forms.EmailField(label='אימייל לאישור', required=True)
    password = forms.CharField(label='סיסמה', widget=forms.PasswordInput)
    confirm_password = forms.CharField(label='אישור סיסמה', widget=forms.PasswordInput)
    bot_check = forms.IntegerField(label='בדיקת אבטחה: כמה זה 3 + 4?', help_text='הכנס את התשובה במספרים כדי לוודא שאינך בוט')
    terms_accepted = forms.BooleanField(
        label='אני מאשר/ת את תנאי השימוש ומדיניות הפרטיות',
        required=True,
        error_messages={'required': 'חובה לאשר את תנאי השימוש כדי להירשם.'}
    )

    class Meta:
        model = User
        fields = ['username', 'email']
        labels = {
            'username': 'שם משתמש',
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
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
        if answer != 7:
            raise ValidationError('תשובה שגויה לבדיקת הבוטים. נסה שוב.')
        return answer

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', 'הסיסמאות אינן תואמות.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user