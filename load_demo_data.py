import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from django.contrib.auth.models import User
from courses.models import (
    Course, Enrollment, Feedback, StatusUpdate,
    StudentProfile, TeacherProfile
)

EXAMINER_PASSWORD = os.environ.get('DEMO_EXAMINER_PASSWORD', 'testpass123')
DEMO_PASSWORD = os.environ.get('DEMO_PASSWORD', 'demo123')
ADMIN_PASSWORD = os.environ.get('DEMO_ADMIN_PASSWORD')
if not ADMIN_PASSWORD and settings.DEBUG:
    ADMIN_PASSWORD = 'admin123'

print("Creating demo data...")

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_or_create_teacher(username, email, password, first_name, last_name, **profile_data):
    """Create a teacher User + TeacherProfile, or return existing."""
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'email': email,
            'first_name': first_name,
            'last_name': last_name
        }
    )
    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    user.set_password(password)
    user.save()
    if created:
        print(f"   Created user: {username}")
    else:
        print(f"   User already exists: {username}")

    # Teachers are not students — remove StudentProfile if signal created one
    if hasattr(user, 'student_profile'):
        user.student_profile.delete()

    profile, prof_created = TeacherProfile.objects.get_or_create(
        user=user,
        defaults=profile_data
    )
    if not prof_created:
        for key, value in profile_data.items():
            setattr(profile, key, value)
        profile.save()

    return user


def get_or_create_student(username, email, password, first_name, last_name, **profile_data):
    """Create a student User + StudentProfile, or return existing."""
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'email': email,
            'first_name': first_name,
            'last_name': last_name
        }
    )
    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    user.set_password(password)
    user.save()
    if created:
        print(f"   Created user: {username}")
    else:
        print(f"   User already exists: {username}")

    # StudentProfile is created by the post_save signal automatically
    profile, prof_created = StudentProfile.objects.get_or_create(
        user=user,
        defaults=profile_data
    )
    if not prof_created:
        for key, value in profile_data.items():
            setattr(profile, key, value)
        profile.save()

    return user


# ============================================
# EXAMINER TEST ACCOUNTS
# ============================================

print("\n Creating examiner test accounts...")

if ADMIN_PASSWORD:
    admin_user, admin_created = User.objects.get_or_create(username='admin')
    admin_user.email = 'admin@test.com'
    admin_user.is_staff = True
    admin_user.is_superuser = True
    admin_user.set_password(ADMIN_PASSWORD)
    admin_user.save()
    StudentProfile.objects.filter(user=admin_user).delete()
    if admin_created:
        print("   Created superuser: admin")
    else:
        print("   Updated superuser: admin")
else:
    print("   Skipped superuser: set DEMO_ADMIN_PASSWORD to provision one")

teacher1 = get_or_create_teacher(
    username='teacher1',
    email='teacher1@test.com',
    password=EXAMINER_PASSWORD,
    first_name='Test',
    last_name='Teacher',
    bio='Test teacher account for examiner evaluation.',
    qualifications='PhD in Computer Science',
    subject_expertise='Django, Python, Web Development',
    years_of_experience=5,
    phone_number='+1-555-TEST',
    office_hours='Available for testing'
)

student1 = get_or_create_student(
    username='student1',
    email='student1@test.com',
    password=EXAMINER_PASSWORD,
    first_name='Test',
    last_name='Student',
    organization='University of London',
    bio='Test student account for examiner evaluation.',
    date_of_birth='2000-01-01'
)

print("Examiner test accounts ready")

# ============================================
# DEMO TEACHERS
# ============================================

print("\n Creating demo teachers...")

sarah = get_or_create_teacher(
    username='sarah_johnson',
    email='sarah@example.com',
    password=DEMO_PASSWORD,
    first_name='Sarah',
    last_name='Johnson',
    bio='Experienced Python instructor with 10 years of teaching experience.',
    qualifications='PhD in Computer Science',
    subject_expertise='Python, Programming Fundamentals, Software Engineering',
    years_of_experience=10,
    phone_number='+1-555-0101',
    office_hours='Mon-Wed 2-4 PM'
)

michael = get_or_create_teacher(
    username='michael_chen',
    email='michael@example.com',
    password=DEMO_PASSWORD,
    first_name='Michael',
    last_name='Chen',
    bio='Full-stack developer and Django expert. Love teaching web development.',
    qualifications='MSc in Software Engineering',
    subject_expertise='Django, Web Development, JavaScript, Databases',
    years_of_experience=8,
    phone_number='+1-555-0102',
    office_hours='Tue-Thu 1-3 PM'
)

emily = get_or_create_teacher(
    username='emily_williams',
    email='emily@example.com',
    password=DEMO_PASSWORD,
    first_name='Emily',
    last_name='Williams',
    bio='Data scientist passionate about making complex topics accessible.',
    qualifications='PhD in Statistics',
    subject_expertise='Data Science, Machine Learning, Statistics, Python',
    years_of_experience=12,
    phone_number='+1-555-0103',
    office_hours='Mon-Fri 10-11 AM'
)

print("Teachers ready")

# ============================================
# DEMO STUDENTS
# ============================================

print("\n Creating demo students...")

alice = get_or_create_student(
    username='alice_smith',
    email='alice@example.com',
    password=DEMO_PASSWORD,
    first_name='Alice',
    last_name='Smith',
    organization='University of London',
    bio='Computer Science student interested in web development and AI.',
    date_of_birth='2002-03-15'
)

bob = get_or_create_student(
    username='bob_johnson',
    email='bob@example.com',
    password=DEMO_PASSWORD,
    first_name='Bob',
    last_name='Johnson',
    organization='Tech Academy',
    bio='Aspiring software developer learning Python and Django.',
    date_of_birth='2001-07-22'
)

carol = get_or_create_student(
    username='carol_martinez',
    email='carol@example.com',
    password=DEMO_PASSWORD,
    first_name='Carol',
    last_name='Martinez',
    organization='Online Learners Community',
    bio='Self-taught programmer transitioning to data science.',
    date_of_birth='1998-11-30'
)

david = get_or_create_student(
    username='david_lee',
    email='david@example.com',
    password=DEMO_PASSWORD,
    first_name='David',
    last_name='Lee',
    organization='University of London',
    bio='Part-time student working in tech industry.',
    date_of_birth='2000-05-08'
)

print("Students ready")

# ============================================
# COURSES — every teacher gets courses
# instructor_name and instructor_email are derived properties from
# created_by — they must NOT be passed as arguments here.
# ============================================

print("\n Creating courses...")

course1, _ = Course.objects.get_or_create(
    title="Introduction to Python",
    defaults={
        'description': (
            "Learn Python programming from scratch. Perfect for beginners! "
            "Covers variables, loops, functions, and object-oriented programming."
        ),
        'created_by': sarah
    }
)

course2, _ = Course.objects.get_or_create(
    title="Web Development with Django",
    defaults={
        'description': (
            "Build modern web applications using Django framework. "
            "Learn MVC, templates, forms, authentication, and deployment."
        ),
        'created_by': michael
    }
)

course3, _ = Course.objects.get_or_create(
    title="Data Science Fundamentals",
    defaults={
        'description': (
            "Introduction to data analysis, statistics, and machine learning. "
            "Use Python libraries like pandas, numpy, and scikit-learn."
        ),
        'created_by': emily
    }
)

course4, _ = Course.objects.get_or_create(
    title="Advanced Python Programming",
    defaults={
        'description': (
            "Deep dive into advanced Python concepts: decorators, generators, "
            "context managers, metaclasses, and async programming."
        ),
        'created_by': sarah
    }
)

# teacher1 examiner course — gives the examiner teacher account real content to manage
course5, _ = Course.objects.get_or_create(
    title="Full Stack Web Development",
    defaults={
        'description': (
            "A comprehensive course covering both front-end and back-end development. "
            "Build complete web applications using Django, HTML, CSS, and JavaScript."
        ),
        'created_by': teacher1
    }
)

# michael gets a second course
course6, _ = Course.objects.get_or_create(
    title="REST APIs with Django REST Framework",
    defaults={
        'description': (
            "Learn to build professional REST APIs using Django REST Framework. "
            "Covers serializers, ViewSets, authentication, and API documentation."
        ),
        'created_by': michael
    }
)

# emily gets a second course
course7, _ = Course.objects.get_or_create(
    title="Machine Learning with Python",
    defaults={
        'description': (
            "Practical introduction to machine learning algorithms. "
            "Build and evaluate models using scikit-learn, pandas, and matplotlib."
        ),
        'created_by': emily
    }
)

print("Courses ready")

# ============================================
# ENROLLMENTS — every student enrolled in multiple courses
# including student1 in teacher1's course for examiner testing
# ============================================

print("\n Creating enrollments...")

enrollments = [
    # alice enrolled in 3 courses
    (course1, alice),
    (course2, alice),
    (course6, alice),
    # bob enrolled in 3 courses
    (course1, bob),
    (course3, bob),
    (course7, bob),
    # carol enrolled in 3 courses
    (course2, carol),
    (course3, carol),
    (course5, carol),
    # david enrolled in 3 courses
    (course4, david),
    (course5, david),
    (course6, david),
    # student1 enrolled in teacher1's course + 2 others for examiner testing
    (course5, student1),
    (course1, student1),
    (course2, student1),
    # extra enrollments to make manage students interesting
    (course5, alice),
    (course5, bob),
]

for course, student in enrollments:
    _, created = Enrollment.objects.get_or_create(
        course=course,
        student=student
    )
    if created:
        print(f"   Enrolled {student.username} in '{course.title}'")

print("Enrollments ready")

# ============================================
# FEEDBACK — ratings across all courses
# ============================================

print("\n Creating feedback...")

feedback_data = [
    (course1, alice,   5, "Excellent course! Very well explained. Sarah is an amazing instructor."),
    (course1, bob,     5, "Best Python course I've taken. Clear explanations and practical examples."),
    (course1, student1,4, "Great intro to Python. Very clear for beginners."),
    (course2, alice,   4, "Loved the Django content. Templates and forms section was especially helpful."),
    (course2, carol,   5, "Michael really knows his stuff. Best web dev course available."),
    (course2, student1,4, "Really practical course, learned a lot about Django quickly."),
    (course3, bob,     4, "Great content, learned a lot about Django. Challenging but rewarding."),
    (course3, carol,   5, "Fantastic introduction to data science! Hands-on approach really helped."),
    (course4, david,   5, "Mind-blowing advanced content. Decorators and generators finally make sense!"),
    (course5, carol,   4, "Great full stack overview. Covers everything you need to get started."),
    (course5, david,   5, "Excellent course for building complete web apps from scratch."),
    (course5, student1,5, "Test Teacher explains everything very clearly. Highly recommended!"),
    (course6, alice,   5, "DRF is complex but this course breaks it down perfectly."),
    (course6, david,   4, "Solid API course. The ViewSets section saved me hours of work."),
    (course7, bob,     4, "Great practical ML course. The scikit-learn examples were very useful."),
]

for course, student, rating, comment in feedback_data:
    existing_feedback = Feedback.objects.filter(
        course=course,
        student=student,
        rating=rating,
        comment=comment,
    ).exists()
    created = not existing_feedback
    if created:
        Feedback.objects.create(
            course=course,
            student=student,
            rating=rating,
            comment=comment,
        )
    if created:
        print(f"   Feedback from {student.username} on '{course.title}'")

print("Feedback ready")

# ============================================
# STATUS UPDATES — all users have posts
# ============================================

print("\n Creating status updates...")

status_data = [
    (alice,    "Just started learning Python! So excited to join this platform."),
    (alice,    "Finished the Django course today. Ready to build my first real project!"),
    (bob,      "Completed my first Django project today! Built a simple blog. Feels amazing!"),
    (bob,      "Data science is next on my list. Can't wait to start with pandas."),
    (carol,    "Data science is harder than I thought, but I'm determined to master it."),
    (carol,    "Just enrolled in the Full Stack course. This platform has so much to offer!"),
    (david,    "Working through the Advanced Python course. Decorators are mind-blowing!"),
    (david,    "Completed the REST APIs course. Built my first API today!"),
    (sarah,    "Welcome to all new students! Don't hesitate to ask questions in the course chat."),
    (sarah,    "New course content uploaded for Advanced Python. Check it out!"),
    (michael,  "Just updated the Django course with new material on class-based views."),
    (emily,    "Office hours today 10-11am. Come with your data science questions!"),
    (teacher1, "Welcome everyone! My Full Stack course is now open for enrollment."),
    (student1, "Just enrolled in the Full Stack course. Looking forward to learning!"),
]

for author, content in status_data:
    _, created = StatusUpdate.objects.get_or_create(
        author=author,
        content=content
    )
    if created:
        print(f"   Status from {author.username}")

print("Status updates ready")

# ============================================
# SUMMARY
# ============================================

print("\n" + "=" * 50)
print("DEMO DATA LOADED SUCCESSFULLY!")
print("=" * 50)
print(f"\nSummary:")
print(f"   Teachers:       {User.objects.filter(teacher_profile__isnull=False).count()}")
print(f"   Students:       {User.objects.filter(student_profile__isnull=False).count()}")
print(f"   Courses:        {Course.objects.count()}")
print(f"   Enrollments:    {Enrollment.objects.count()}")
print(f"   Feedback:       {Feedback.objects.count()}")
print(f"   Status Updates: {StatusUpdate.objects.count()}")

print("\nDemo account credentials were loaded from environment variables or safe demo defaults.")
print("See README.md for the local-only defaults; passwords are not written to deployment logs.")
print("\n" + "=" * 50 + "\n")
