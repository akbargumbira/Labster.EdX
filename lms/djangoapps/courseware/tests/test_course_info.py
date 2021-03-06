"""
Test the course_info xblock
"""
from django.core.urlresolvers import reverse
from django.test.utils import override_settings
import mock
from opaque_keys.edx.locations import SlashSeparatedCourseKey

from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.django_utils import (
    TEST_DATA_MOCK_MODULESTORE, TEST_DATA_MIXED_CLOSED_MODULESTORE
)
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory

from .helpers import LoginEnrollmentTestCase


class CourseInfoTestCase(LoginEnrollmentTestCase, ModuleStoreTestCase):
    """
    Tests for the Course Info page
    """
    def setUp(self):
        super(CourseInfoTestCase, self).setUp()
        self.course = CourseFactory.create()
        self.page = ItemFactory.create(
            category="course_info", parent_location=self.course.location,
            data="OOGIE BLOOGIE", display_name="updates"
        )

    def test_logged_in_unenrolled(self):
        self.setup_user()
        url = reverse('info', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("OOGIE BLOOGIE", resp.content)
        self.assertIn("You are not currently enrolled in this course", resp.content)

    def test_logged_in_enrolled(self):
        self.enroll(self.course)
        url = reverse('info', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertNotIn("You are not currently enrolled in this course", resp.content)

    def test_anonymous_user(self):
        url = reverse('info', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("OOGIE BLOOGIE", resp.content)


class CourseInfoTestCaseXML(LoginEnrollmentTestCase, ModuleStoreTestCase):
    """
    Tests for the Course Info page for an XML course
    """
    MODULESTORE = TEST_DATA_MIXED_CLOSED_MODULESTORE

    # The following XML test course (which lives at common/test/data/2014)
    # is closed; we're testing that a course info page still appears when
    # the course is already closed
    xml_course_key = SlashSeparatedCourseKey('edX', 'detached_pages', '2014')

    # this text appears in that course's course info page
    # common/test/data/2014/info/updates.html
    xml_data = "course info 463139"

    @mock.patch.dict('django.conf.settings.FEATURES', {'DISABLE_START_DATES': False})
    def test_logged_in_xml(self):
        self.setup_user()
        url = reverse('info', args=[self.xml_course_key.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.xml_data, resp.content)

    @mock.patch.dict('django.conf.settings.FEATURES', {'DISABLE_START_DATES': False})
    def test_anonymous_user_xml(self):
        url = reverse('info', args=[self.xml_course_key.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(self.xml_data, resp.content)
