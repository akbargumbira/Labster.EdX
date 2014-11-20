import binascii
import calendar
import json
import os
import re

from datetime import datetime

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models import Count, Q
from django.db.models.signals import pre_save, post_save
from django.utils import timezone

from xmodule_django.models import CourseKeyField, LocationKeyField

PLATFORM_NAME = 'platform'


class Token(models.Model):
    name = models.CharField(max_length=100, unique=True)
    key = models.CharField(max_length=40, unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    @classmethod
    def get_for_platform(self):
        obj, _ = self.objects.get_or_create(name=PLATFORM_NAME)
        return obj

    def __unicode__(self):
        return self.name

    def for_header(self):
        return "Token {}".format(self.key)

    def generate_key(self):
        return binascii.hexlify(os.urandom(20)).decode()

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        super(Token, self).save(*args, **kwargs)


class LanguageLab(models.Model):
    language_code = models.CharField(max_length=4)
    language_name = models.CharField(max_length=32)

    def __unicode__(self):
        return self.language_name


class ActiveManager(models.Manager):
    def get_query_set(self):
        qs = super(ActiveManager, self).get_query_set()
        return qs.filter(is_active=True)


class Lab(models.Model):
    """
    Master Lab
    """
    name = models.CharField(max_length=64)
    description = models.TextField(default='')
    engine_xml = models.CharField(max_length=128, default="")
    engine_file = models.CharField(max_length=128, blank=True, default="labster.unity3d")
    quiz_block_file = models.CharField(max_length=128, default="")
    quiz_block_last_updated = models.DateTimeField(blank=True, null=True)

    demo_course_id = CourseKeyField(max_length=255, db_index=True, blank=True,
                                    null=True)

    use_quiz_blocks = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    verified_only = models.BooleanField(default=False)

    # lab can have many languages
    languages = models.ManyToManyField(LanguageLab)

    created_at = models.DateTimeField(default=timezone.now)
    modified_at = models.DateTimeField(default=timezone.now)

    # unused
    screenshot = models.ImageField(upload_to='edx/labster/lab/images', blank=True)
    screenshot_url = models.URLField(max_length=500, blank=True, default="")
    url = models.URLField(max_length=120, blank=True, default="")
    wiki_url = models.URLField(max_length=120, blank=True, default="")
    questions = models.TextField(default='', blank=True)

    all_objects = models.Manager()
    objects = ActiveManager()

    @classmethod
    def fetch_with_lab_proxies(self):
        labs = Lab.objects.filter(verified_only=False, labproxy__is_active=True)\
            .distinct()\
            .annotate(labproxy_count=Count('labproxy'))
        return labs

    @classmethod
    def update_quiz_block_last_updated(self, lab_id):
        Lab.objects.filter(id=lab_id).update(quiz_block_last_updated=timezone.now())

    def __unicode__(self):
        return self.name

    def to_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'template_location': '',
        }

    @property
    def slug(self):
        """
        converts `Engine_CrimeScene_OVR.xml`
        to `CrimeScene_OVR`
        """

        try:
            return self.engine_xml.split('Engine_')[1].split('.xml')[0]
        except:
            return ''

    @property
    def studio_detail_url(self):
        return "/labster/labs/{}/".format(self.id)

    @property
    def new_quiz_block_url(self):
        return reverse('labster_create_quiz_block', args=[self.id])

    def get_quizblocks(self):
        return self.quizblocklab_set.all()


class QuizBlock(models.Model):
    """
    Master QuizBlock
    """
    lab = models.ForeignKey(Lab)
    element_id = models.CharField(max_length=100, db_index=True)

    time_limit = models.IntegerField(blank=True, null=True)
    order = models.IntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    modified_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('lab', 'element_id')
        ordering = ('order', 'created_at')

    def __unicode__(self):
        return "{}: {}".format(self.lab.name, self.element_id)


class Scale(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __unicode__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __unicode__(self):
        return self.name


class Problem(models.Model):
    """
    Master Problem
    """
    quiz_block = models.ForeignKey(QuizBlock)
    element_id = models.CharField(max_length=100, db_index=True)

    sentence = models.TextField()
    correct_message = models.TextField(default="")
    wrong_message = models.TextField(default="")
    hashed_sentence = models.CharField(max_length=50, default="", db_index=True)

    no_score = models.BooleanField(default=False)
    max_attempts = models.IntegerField(blank=True, null=True)
    randomize_option_order = models.BooleanField(default=True)
    order = models.IntegerField(default=0)

    is_adaptive = models.BooleanField(default=False)

    # adaptive fields
    ANSWER_TYPE_CHOICES = (
        (1, 'dichotomous'),
        (2, '3 response options'),
        (3, '4 response options'),
        # (4, '5 response options'),
        # (5, '6 response options'),
    )
    answer_type = models.IntegerField(choices=ANSWER_TYPE_CHOICES, blank=True, null=True)
    number_of_destractors = models.IntegerField(blank=True, null=True)
    content = models.TextField(default="")
    feedback = models.TextField(default="")
    time = models.FloatField(blank=True, null=True)
    sd_time = models.FloatField(blank=True, null=True)
    discrimination = models.IntegerField(blank=True, null=True)
    guessing = models.FloatField(blank=True, null=True)
    image_url = models.URLField(max_length=500, blank=True, default="")
    scales = models.ManyToManyField(Scale, blank=True)
    categories = models.ManyToManyField(Category, blank=True)
    # end of adaptive fields

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    modified_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('quiz_block', 'element_id')
        ordering = ('order', 'created_at')

    def __unicode__(self):
        return "{}: {}".format(self.quiz_block, self.element_id)

    @property
    def correct_answer(self):
        try:
            return Answer.objects.get(is_active=True, problem=self, is_correct=True)
        except Answer.DoesNotExist:
            return None

    @property
    def correct_answer_text(self):
        if self.correct_answer:
            return self.correct_answer.text
        return ""


class AdaptiveProblemManager(models.Manager):
    def get_query_set(self):
        qs = super(AdaptiveProblemManager, self).get_query_set()
        qs = qs.filter(is_adaptive=True)
        return qs


class AdaptiveProblem(Problem):
    objects = AdaptiveProblemManager()

    class Meta:
        proxy = True


class Answer(models.Model):
    """
    Master Answer
    """

    problem = models.ForeignKey(Problem)
    text = models.TextField()
    hashed_text = models.CharField(max_length=50, db_index=True)
    is_correct = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    # for adaptive
    difficulty = models.IntegerField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    modified_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('problem', 'hashed_text')
        ordering = ('order', 'created_at')

    def __unicode__(self):
        return "{}: {} ({})".format(
            self.problem,
            self.text,
            "correct" if self.is_correct else "incorrect")


class LabProxy(models.Model):
    """
    Stores connection between subsection and lab
    """

    lab = models.ForeignKey(Lab, blank=True, null=True)
    location = models.CharField(max_length=200, unique=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(default=timezone.now)
    modified_at = models.DateTimeField(default=timezone.now)

    all_objects = models.Manager()
    objects = ActiveManager()

    class Meta:
        verbose_name_plural = 'Lab proxies'

    @property
    def course_from_location(self):
        paths = self.location.split('/')
        return '/'.join([paths[2], paths[3]])


class UserSave(models.Model):
    """
    SavePoint need to be linked to LabProxy instead of Lab

    The way we designed the system, many courses could use same lab,
    with different set of questions.
    """
    lab_proxy = models.ForeignKey(LabProxy)
    user = models.ForeignKey(User)
    save_file = models.FileField(blank=True, null=True, upload_to='edx/labster/lab/save')
    created_at = models.DateTimeField(default=timezone.now)
    modified_at = models.DateTimeField(default=timezone.now)

    # these will be deleted
    play_count = models.IntegerField(default=0)
    is_finished = models.BooleanField(default=False)

    class Meta:
        unique_together = ('lab_proxy', 'user')

    def get_new_save_file_name(self):
        timestamp = calendar.timegm(datetime.utcnow().utctimetuple())
        file_name = "{}_{}_{}.zip".format(timestamp, self.lab_proxy_id, self.user_id)
        return file_name


class UserAttemptManager(models.Manager):
    def latest_for_user(self, lab_proxy, user):
        try:
            return self.get_query_set().filter(
                lab_proxy=lab_proxy, user=user).latest('created_at')
        except self.model.DoesNotExist:
            return None


class UserAttempt(models.Model):
    lab_proxy = models.ForeignKey(LabProxy)
    user = models.ForeignKey(User)
    is_finished = models.BooleanField(default=False)

    created_at = models.DateTimeField(default=timezone.now)
    modified_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(blank=True, null=True)

    objects = UserAttemptManager()

    @property
    def play(self):
        return 0

    def mark_finished(self):
        self.is_finished = True
        self.finished_at = timezone.now()
        self.save()

    def get_total_play_count(self):
        return UserAttempt.objects.filter(
            user=self.user, lab_proxy=self.lab_proxy).count()


class ErrorInfo(models.Model):
    user = models.ForeignKey(User)
    lab_proxy = models.ForeignKey(LabProxy)
    browser = models.CharField(max_length=64, blank=True, default="")
    os = models.CharField(max_length=32, blank=True, default="")
    user_agent = models.CharField(max_length=200, blank=True, default="")
    message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)


class DeviceInfo(models.Model):
    user = models.ForeignKey(User)
    lab_proxy = models.ForeignKey(LabProxy)

    cores = models.CharField(default="", max_length=128, blank=True)
    device_id = models.CharField(default="", max_length=128, blank=True)
    fill_rate = models.CharField(default="", max_length=128, blank=True)
    frame_rate = models.CharField(default="", max_length=128, blank=True)
    gpu = models.CharField(default="", max_length=128, blank=True)
    machine_type = models.CharField(default="", max_length=128, blank=True)
    memory = models.CharField(default="", max_length=128, blank=True)
    misc = models.TextField(default="", blank=True)
    os = models.CharField(default="", max_length=32, blank=True)
    processor = models.CharField(default="", max_length=128, blank=True)
    quality = models.CharField(default="", max_length=128, blank=True)
    ram = models.CharField(default="", max_length=32, blank=True)
    shader_level = models.CharField(default="", max_length=128, blank=True)

    created_at = models.DateTimeField(default=timezone.now)


class UnityLogManager(models.Manager):

    def get_query_set(self):
        qs = super(UnityLogManager, self).get_query_set()
        return qs.exclude(log_type='UNITY_LOG')


def separate_tag_from_message(message):
    tag = ''
    search = re.search(r'^\[(\w+)\] (.+)', message)
    if search:
        tag, message = search.groups()
    return tag, message


class UnityLog(models.Model):
    user = models.ForeignKey(User, blank=True, null=True)
    lab_proxy = models.ForeignKey(LabProxy, blank=True, null=True)

    log_type = models.CharField(max_length=100, db_index=True)
    url = models.CharField(max_length=255, default='')
    request_method = models.CharField(max_length=10, blank=True, default='')
    message = models.TextField(help_text="JSON representation of data")
    tag = models.CharField(max_length=50, default="INFO", db_index=True)

    created_at = models.DateTimeField(default=timezone.now)
    objects = UnityLogManager()

    def get_message(self):
        if self.message:
            return json.loads(self.message)
        return None

    def set_message(self, message):
        self.message = json.dumps(message)

    def save(self, *args, **kwargs):
        self.log_type = self.log_type.strip().upper()
        return super(UnityLog, self).save(*args, **kwargs)

    @classmethod
    def new(self, user, lab_proxy, log_type, message, url='', request_method=''):
        message = json.dumps(message)
        return self.objects.create(
            user=user, lab_proxy=lab_proxy,
            log_type=log_type, message=message, url=url, request_method=request_method)

    @classmethod
    def new_unity_log(self, user, lab_proxy, message, url='', request_method=''):
        tag, message = separate_tag_from_message(message)
        return self.objects.create(
            user=user,
            lab_proxy=lab_proxy,
            log_type='UNITY_LOG',
            message=message,
            tag=tag,
            url=url,
            request_method=request_method)


class UnityPlatformLogManager(models.Manager):

    def get_query_set(self):
        qs = super(UnityPlatformLogManager, self).get_query_set()
        return qs.filter(log_type='UNITY_LOG')


class UnityPlatformLog(UnityLog):
    objects = UnityPlatformLogManager()
    class Meta:
        proxy = True


class ProblemProxy(models.Model):
    """
    Model to store connection between quiz and the location
    """

    lab_proxy = models.ForeignKey(LabProxy)
    problem = models.ForeignKey(Problem, blank=True, null=True)
    location = LocationKeyField(max_length=255, db_index=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    # FIXME: delete
    quiz_id = models.CharField(max_length=100, db_index=True)
    question = models.CharField(max_length=100, db_index=True, help_text='Question in md5')
    question_text = models.TextField(default='')
    location = models.CharField(max_length=200)
    correct_answer = models.TextField()

    def __unicode__(self):
        return str(self.id)


class UserAnswer(models.Model):
    user = models.ForeignKey(User)

    lab_proxy = models.ForeignKey(LabProxy, blank=True, null=True)
    problem = models.ForeignKey(Problem, blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)

    quiz_id = models.CharField(max_length=100, blank=True, default='')
    question = models.TextField(default='')
    answer_string = models.TextField(default='')
    correct_answer = models.TextField(default='')
    is_correct = models.BooleanField(default=True)

    start_time = models.DateTimeField(blank=True, null=True)
    end_time = models.DateTimeField(blank=True, null=True)
    completion_time = models.FloatField(blank=True, null=True)

    attempt_count = models.IntegerField(blank=True, null=True)
    play_count = models.IntegerField(blank=True, null=True)

    score = models.IntegerField(blank=True, null=True)

    is_view_theory_clicked = models.BooleanField(default=False)

    # FIXME: delete
    problem_proxy = models.ForeignKey(ProblemProxy, blank=True, null=True)


# FIXME: unused
def fetch_labs_as_json():
    labs = Lab.objects.order_by('name')
    labs_json = [lab.to_json() for lab in labs]
    return labs_json


def get_or_create_lab_proxy(location, lab=None):
    location = location.strip()
    try:
        lab_proxy = LabProxy.objects.get(location=location)
        created = False
    except LabProxy.DoesNotExist:
        lab_proxy = LabProxy(location=location)
        created = True

    modified = all([lab is not None, lab_proxy.lab is not lab])
    if modified:
        lab_proxy.lab = lab

    if created or modified:
        lab_proxy.save()

    return lab_proxy


# FIXME: update post save for Lab
# def create_master_lab(sender, instance, created, **kwargs):
#     from labster.quiz_blocks import update_master_lab
#     update_master_lab(instance)
# post_save.connect(create_master_lab, sender=Lab)


def update_modified_at(sender, instance, **kwargs):
    instance.modified_at = timezone.now()
pre_save.connect(update_modified_at, sender=Lab)
pre_save.connect(update_modified_at, sender=QuizBlock)
pre_save.connect(update_modified_at, sender=Problem)
pre_save.connect(update_modified_at, sender=Answer)
pre_save.connect(update_modified_at, sender=LabProxy)
pre_save.connect(update_modified_at, sender=UserSave)
pre_save.connect(update_modified_at, sender=Lab)


class LabsterUserLicense(models.Model):
    """
    Tracks user's licenses against course
    """
    course_id = CourseKeyField(max_length=255, db_index=True)
    email = models.EmailField(max_length=255)

    created_at = models.DateTimeField(default=timezone.now)
    expired_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('course_id', 'email')

    @classmethod
    def course_licenses_count(cls, course_id):
        now = timezone.now()
        no_expired = {'course_id': course_id, 'expired_at': None}
        expired = {'course_id': course_id, 'expired_at__gte': now}
        return cls.objects.filter(Q(**no_expired) | Q(**expired)).count()

    def __unicode__(self):
        return "{} - {}".format(self.course_id, self.email)

    @property
    def is_expired(self):
        return self.expired_at and timezone.now() > self.expired_at

    def renew_to(self, expired_at):
        self.expired_at = expired_at
        self.save()


class LabsterCourseLicense(models.Model):
    user = models.ForeignKey(User)  # the teacher
    course_id = CourseKeyField(max_length=255, db_index=True)
    license_id = models.IntegerField(unique=True)

    class Meta:
        unique_together = ('user', 'course_id')
