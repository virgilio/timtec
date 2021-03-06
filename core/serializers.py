from django.contrib.flatpages.models import FlatPage
from django.contrib.auth import get_user_model
from core.models import (Course, CourseProfessor, CourseStudent, Lesson,
                         Video, StudentProgress, Unit, ProfessorMessage,
                         ProfessorMessageRead, Class, CourseAuthor,
                         CourseCertification, CertificationProcess, Evaluation,
                         CertificateTemplate, IfCertificateTemplate)
from accounts.serializers import TimtecUserSerializer, \
    TimtecUserAdminCertificateSerializer
from activities.models import Activity, Answer
from activities.serializers import ActivitySerializer, AnswerSerializer
from notes.models import Note
from rest_framework import serializers


class ProfessorMessageReadSerializer(serializers.ModelSerializer):

    class Meta:
        model = ProfessorMessageRead
        fields = ('id', 'message', 'is_read')


class ProfessorMessageSerializer(serializers.ModelSerializer):

    professor = TimtecUserSerializer(read_only=True)
    course_slug = serializers.SerializerMethodField(read_only=True)
    course_name = serializers.SerializerMethodField(read_only=True)
    is_read = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProfessorMessage
        fields = ('id', 'course', 'course_name', 'course_slug', 'professor', 'users', 'subject', 'message', 'date', 'is_read')

    def get_course_slug(self, obj):
        try:
            return obj.course.slug
        except AttributeError as e:
            return ''  # no course is associated with this message

    def get_course_name(self, obj):
        try:
            return obj.course.name
        except AttributeError as e:
            return ''  # no course is associated with this message

    def get_is_read(self, obj):
        try:
            read_state = ProfessorMessageRead.objects.get(user=self.context['request'].user, message=obj)
            return read_state.is_read
        except ProfessorMessageRead.DoesNotExist as e:
            return False


class ProfessorGlobalMessageSerializer(ProfessorMessageSerializer):
    users = TimtecUserSerializer(read_only=True, required=False, many=True)

    def create(self, validated_data):

        all_students = self.context['request'].data.get('all_students', None)
        groups = self.context['request'].data.get('groups', None)

        recipients = self.context['request'].data.get('users', None)
        validated_data['professor'] = self.context['request'].user

        global_message = ProfessorMessage(**validated_data)
        global_message.save()

        User = get_user_model()
        if all_students:
            # If all_students was set to True by the client, this is a global message
            global_message.users.add(*[user for user in User.objects.all()])
        elif groups:
            # If groups were specified, their users are the recipients
            global_message.users.add(*[user for user in User.objects.filter(groups__in=groups)])
        elif recipients:
            # Otherwise, user the recipients list
            for user_id in self.context['request'].data['users']:
                global_message.users.add(User.objects.get(id=user_id))

        global_message.send()
        return global_message


class BaseCourseSerializer(serializers.ModelSerializer):
    professors = serializers.SerializerMethodField('get_professor_name')
    home_thumbnail_url = serializers.SerializerMethodField()
    is_assistant_or_coordinator = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ("id", "slug", "name", "status", "home_thumbnail_url",
                  "start_date", "home_published", "has_started",
                  "min_percent_to_complete", "professors", "is_assistant_or_coordinator",)

    @staticmethod
    def get_professor_name(obj):
        if obj.course_authors.all():
            return [author.get_name() for author in obj.course_authors.all()]
        return ''

    @staticmethod
    def get_home_thumbnail_url(obj):
        if obj.home_thumbnail:
            return obj.home_thumbnail.url
        return ''

    def get_is_assistant_or_coordinator(self, obj):
        if self.context:
            return obj.is_assistant_or_coordinator(self.context['request'].user)


class BaseClassSerializer(serializers.ModelSerializer):

    class Meta:
        model = Class
        fields = ("id", "name", "assistants", "user_can_certificate")


class BaseEvaluationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Evaluation


class BaseCertificationProcessSerializer(serializers.ModelSerializer):
    evaluation = BaseEvaluationSerializer()

    class Meta:
        model = CertificationProcess


class BaseCourseCertificationSerializer(serializers.ModelSerializer):

    class Meta:
        model = CourseCertification


class CertificationProcessSerializer(serializers.ModelSerializer):
    course_certification = serializers.SlugRelatedField(slug_field="link_hash", read_only=True)

    class Meta:
        model = CertificationProcess


class CourseCertificationSerializer(serializers.ModelSerializer):
    processes = BaseCertificationProcessSerializer(many=True, read_only=True)
    approved = BaseCertificationProcessSerializer(source='get_approved_process', read_only=True)
    course = serializers.SerializerMethodField()
    url = serializers.ReadOnlyField(source='get_absolute_url')

    class Meta:
        model = CourseCertification
        fields = ('link_hash', 'created_date', 'is_valid', 'processes', 'type',
                  'approved', 'course', 'url')

    @staticmethod
    def get_course(obj):
        return obj.course.id


class EvaluationSerializer(serializers.ModelSerializer):
    processes = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = Evaluation


class CertificateTemplateSerializer(serializers.ModelSerializer):

    class Meta:
        model = CertificateTemplate
        fields = ('id', 'course', 'organization_name', 'base_logo_url', 'cert_logo_url', 'role', 'name', 'signature_url', )


class IfCertificateTemplateSerializer(CertificateTemplateSerializer):

    class Meta:
        model = IfCertificateTemplate
        fields = ('id', 'course', 'organization_name', 'base_logo_url', 'cert_logo_url',
                  'pronatec_logo', 'mec_logo', 'role', 'name', 'signature_url',)


class CertificateTemplateImageSerializer(serializers.ModelSerializer):

    class Meta:
        model = CertificateTemplate
        fields = ('base_logo', 'cert_logo', 'signature', )


class ClassActivitySerializer(serializers.ModelSerializer):
    activity_answers = serializers.SerializerMethodField()

    class Meta:
        model = Class
        fields = ['id', 'name', 'activity_answers', 'course']

    def get_activity_answers(self, obj):
        request = self.context.get("request")
        activity_id = request.query_params.get('activity', None)

        try:
            queryset = Answer.objects.filter(
                activity=activity_id,
                activity__unit__lesson__course=obj.course,
                user__in=obj.students.all()
            ).exclude(user=request.user)
        except Answer.DoesNotExist:
            return

        return AnswerSerializer(
            queryset, many=True, **{'context': self.context}).data


class VideoSerializer(serializers.ModelSerializer):

    class Meta:
        model = Video
        fields = ('id', 'name', 'youtube_id',)


class CourseSerializer(serializers.ModelSerializer):

    intro_video = VideoSerializer(required=False)
    home_thumbnail_url = serializers.SerializerMethodField()
    professors = TimtecUserSerializer(read_only=True, many=True)
    is_user_assistant = serializers.SerializerMethodField()
    is_user_coordinator = serializers.SerializerMethodField()
    is_assistant_or_coordinator = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ("id", "slug", "name", "intro_video", "application", "requirement",
                  "abstract", "structure", "workload", "pronatec", "status",
                  "thumbnail_url", "home_thumbnail_url", "home_position",
                  "start_date", "home_published", "authors_names", "has_started",
                  "min_percent_to_complete", "is_user_assistant", "is_user_coordinator",
                  "is_assistant_or_coordinator", 'professors', )

    @staticmethod
    def get_home_thumbnail_url(obj):
        if obj.home_thumbnail:
            return obj.home_thumbnail.url
        return ''

    def get_is_user_assistant(self, obj):
        return obj.is_course_assistant(self.context['request'].user)

    def get_is_user_coordinator(self, obj):
        return obj.is_course_coordinator(self.context['request'].user)

    def get_is_assistant_or_coordinator(self, obj):
        return obj.is_assistant_or_coordinator(self.context['request'].user)

    def update(self, instance, validated_data):
        intro_video_data = validated_data.pop('intro_video', None)

        course = super(CourseSerializer, self).update(instance, validated_data)

        if intro_video_data:
            intro_video_ser = VideoSerializer(course.intro_video, data=intro_video_data)
            if intro_video_ser.is_valid():
                intro_video = intro_video_ser.save()
            course.intro_video = intro_video
            course.save()

        return course


class CourseStudentSerializer(serializers.ModelSerializer):
    user = TimtecUserSerializer(read_only=True)

    course_finished = serializers.BooleanField()
    can_emmit_receipt = serializers.BooleanField()
    percent_progress = serializers.IntegerField()
    min_percent_to_complete = serializers.IntegerField()

    current_class = BaseClassSerializer(source='get_current_class')
    course = BaseCourseSerializer()
    certificate = CourseCertificationSerializer()
    last_activity = serializers.SerializerMethodField()

    class Meta:
        model = CourseStudent
        fields = ('id', 'user', 'course', 'start_date', 'course_finished',
                  'certificate', 'can_emmit_receipt', 'percent_progress',
                  'current_class', 'min_percent_to_complete', 'last_activity')

    def get_last_activity(self, obj):
        units = []
        [units.extend(lesson.units.all()) for lesson in obj.course.lessons.all()]
        progresses = StudentProgress.objects.filter(unit__in=units, user=obj.user).order_by('-last_access')
        if progresses:
            return progresses[0].last_access
        return None


class CourseStudentClassSerializer(CourseStudentSerializer):

    user = TimtecUserAdminCertificateSerializer(read_only=True)

    class Meta:
        model = CourseStudent
        fields = ('id', 'user', 'course_finished',
                  'certificate', 'can_emmit_receipt', 'percent_progress',)


class ProfileCourseCertificationSerializer(serializers.ModelSerializer):
    course = BaseCourseSerializer()
    approved = serializers.SerializerMethodField()

    class Meta:
        model = CourseCertification
        fields = ('link_hash', 'created_date', 'is_valid', 'processes', 'type',
                  'approved', 'course')

    def get_approved(self, obj):
        return obj.course_student.can_emmit_receipt()


class ClassSerializer(serializers.ModelSerializer):
    students_details = CourseStudentClassSerializer(source='get_students', many=True, read_only=True)
    processes = CertificationProcessSerializer(read_only=True, many=True)
    evaluations = EvaluationSerializer(read_only=True, many=True)
    course = CourseSerializer(read_only=True)
    assistants = TimtecUserSerializer(read_only=True, many=True)

    class Meta:
        model = Class

    def update(self, instance, validated_data, **kwargs):
        assistants = self.context['request'].data.get('assistants', None)
        updated_class = super(ClassSerializer, self).update(instance, validated_data)
        # If there are assistans to be associated with the class, do it now
        updated_class.assistants.clear()
        for assistant in assistants:
            updated_class.assistants.add(assistant['id'])
        return updated_class


class ProfileClassSerializer(serializers.ModelSerializer):
    course = serializers.StringRelatedField()

    class Meta:
        model = Class
        fields = ('id', 'name', 'course')

class ProfileSerializer(TimtecUserSerializer):
    certificates = ProfileCourseCertificationSerializer(many=True,
                                                        source="get_certificates")
    classes = ProfileClassSerializer(many=True)


    class Meta:
        model = get_user_model()
        fields = ('id', 'username', 'name', 'first_name', 'last_name',
                  'biography', 'picture', 'is_profile_filled', 'occupation',
                  'certificates', 'city', 'site', 'occupation', 'classes')


class CourseThumbSerializer(serializers.ModelSerializer):

    class Meta:
        model = Course
        fields = ("id", "thumbnail", "home_thumbnail")


class StudentProgressSerializer(serializers.ModelSerializer):
    complete = serializers.DateTimeField(required=False)
    user = TimtecUserSerializer(read_only=True, required=False)

    class Meta:
        model = StudentProgress
        fields = ('unit', 'complete', 'user',)


class UnitSerializer(serializers.ModelSerializer):
    video = VideoSerializer(required=False, allow_null=True)
    activities = ActivitySerializer(many=True, required=False, allow_null=True)

    class Meta:
        model = Unit
        fields = ('id', 'title', 'video', 'activities', 'side_notes', 'position', 'chat_room',)


class SimpleUnitSerializer(UnitSerializer):
    video = VideoSerializer(required=False, allow_null=True)

    class Meta:
        model = Unit
        fields = ('id', 'title', 'video', 'position',)


class LessonSerializer(serializers.ModelSerializer):

    units = UnitSerializer(many=True)
    is_course_last_lesson = serializers.BooleanField(read_only=True)

    class Meta:
        model = Lesson
        fields = ('id', 'course', 'is_course_last_lesson', 'desc',
                  'name', 'notes', 'position', 'slug', 'status', 'units',
                  'thumbnail')

    def update(self, instance, validated_data):

        units = self.update_units(self.initial_data.get('units'), instance)

        for old_unit in instance.units.all():
            if old_unit not in units:
                old_unit.delete()
            else:
                new_activities = units[units.index(old_unit)].activities
                if old_unit.activities != new_activities:
                    for activity in old_unit.activities:
                        if activity not in new_activities:
                            activity.delete()

        validated_data.pop('units')
        return super(LessonSerializer, self).update(instance, validated_data)

    def create(self, validated_data):
        units_data = validated_data.pop('units')
        new_lesson = super(LessonSerializer, self).create(validated_data)
        # units_data = self.initial_data.get('units')

        self.update_units(units_data, new_lesson)

        return new_lesson

    @classmethod
    def update_units(cls, units_data, lesson):
        units = []
        for unit_data in units_data:
            activities_data = unit_data.pop('activities')
            unit_data.pop('lesson', None)

            video_data = unit_data.pop('video', None)
            if video_data:
                video = Video(**video_data)
                video.save()
            else:
                video = None
            unit = Unit(lesson=lesson, video=video, **unit_data)
            unit.save()
            activities = []
            for activity_data in activities_data:
                activity_id = activity_data.pop('id', None)
                activity, _ = Activity.objects.get_or_create(id=activity_id)
                activity.comment = activity_data.get('comment', None)
                activity.data = activity_data.get('data', None)
                activity.expected = activity_data.get('expected', None)
                activity.type = activity_data.get('type', None)
                activity.unit = unit
                activity.save()
                activities.append(activity)
            unit.activities = activities
            units.append(unit)
        return units


class SimpleLessonSerializer(LessonSerializer):
    units = SimpleUnitSerializer(many=True)


class NoteSerializer(serializers.ModelSerializer):

    class Meta:
        model = Note
        fields = ('id', 'text', 'content_type', 'object_id',)


class UnitNoteSerializer(serializers.ModelSerializer):

    user_note = NoteSerializer()

    class Meta:
        model = Unit
        fields = ('id', 'title', 'video', 'position', 'user_note')
        # fields = ('id', 'title', 'video', 'position')


class LessonNoteSerializer(serializers.ModelSerializer):

    units_notes = UnitNoteSerializer(many=True)
    course = serializers.SlugRelatedField(slug_field='slug', read_only=True)

    class Meta:
        model = Lesson
        fields = ('id', 'name', 'position', 'slug', 'course', 'units_notes',)
        # fields = ('id', 'name', 'position', 'slug', 'course',)


class CourseNoteSerializer(serializers.ModelSerializer):

    lessons_notes = LessonNoteSerializer(many=True)
    course_notes_number = serializers.IntegerField(required=False)

    class Meta:
        model = Course
        fields = ('id', 'slug', 'name', 'lessons_notes', 'course_notes_number',)


class CourseProfessorSerializer(serializers.ModelSerializer):

    user = serializers.PrimaryKeyRelatedField(queryset=get_user_model().objects.all(), required=False)
    user_info = TimtecUserSerializer(source='user', read_only=True)
    course_info = CourseSerializer(source='course', read_only=True)
    get_name = serializers.CharField(read_only=True)
    get_biography = serializers.CharField(read_only=True)
    get_picture_url = serializers.CharField(read_only=True)
    current_user_classes = ClassSerializer(source='get_current_user_classes', read_only=True, many=True)

    class Meta:
        fields = ('id', 'course', 'course_info', 'user', 'name', 'biography', 'picture', 'user_info',
                  'get_name', 'get_biography', 'get_picture_url', 'role', 'current_user_classes',
                  'is_course_author',)
        model = CourseProfessor


class CourseAuthorSerializer(serializers.ModelSerializer):
    user_info = TimtecUserSerializer(source='user', read_only=True)
    course_info = CourseSerializer(source='course', read_only=True)
    # get_name = serializers.Field()
    # get_biography = serializers.Field()
    # get_picture_url = serializers.Field()

    class Meta:
        fields = ('id', 'course', 'course_info', 'name', 'biography', 'picture', 'user_info',
                  'get_name', 'get_biography', 'get_picture_url', 'position')
        model = CourseAuthor


class CourseAuthorPictureSerializer(serializers.ModelSerializer):

    class Meta:
        fields = ('id', 'picture',)
        model = CourseAuthor


class FlatpageSerializer(serializers.ModelSerializer):

    class Meta:
        model = FlatPage
