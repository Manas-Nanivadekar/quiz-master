from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models.quiz import Subject, Chapter, Quiz, Question, Score
from app.models.user import User
from app import db
from datetime import datetime, timedelta
from functools import wraps
from sqlalchemy import or_

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Access denied')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
@admin_required
def dashboard():
    subjects = Subject.query.all()
    users = User.query.filter_by(is_admin=False).all()
    return render_template('admin/dashboard.html', subjects=subjects, users=users)

@admin_bp.route('/search', methods=['GET', 'POST'])
@admin_required
def search():
    query = request.args.get('query', '')
    category = request.args.get('category', 'all')
    
    # Initialize results with all users by default
    results = {
        'users': User.query.filter_by(is_admin=False).all() if not query else [],
        'subjects': [],
        'chapters': [],
        'quizzes': []
    }
    
    # If there's a search query, perform filtered search
    if query:
        # Search users
        if category in ['all', 'users']:
            users = User.query.filter(
                or_(
                    User.email.ilike(f'%{query}%'),
                    User.full_name.ilike(f'%{query}%')
                )
            ).all()
            results['users'] = users
        
        # Search subjects
        if category in ['all', 'subjects']:
            subjects = Subject.query.filter(
                or_(
                    Subject.name.ilike(f'%{query}%'),
                    Subject.description.ilike(f'%{query}%')
                )
            ).all()
            results['subjects'] = subjects
        
        # Search chapters
        if category in ['all', 'chapters']:
            chapters = Chapter.query.filter(
                or_(
                    Chapter.name.ilike(f'%{query}%'),
                    Chapter.description.ilike(f'%{query}%')
                )
            ).all()
            results['chapters'] = chapters
        
        # Search quizzes
        if category in ['all', 'quizzes']:
            quizzes = Quiz.query.filter(
                or_(
                    Quiz.remarks.ilike(f'%{query}%')
                )
            ).all()
            results['quizzes'] = quizzes
    
    return render_template('admin/search.html', results=results, query=query, category=category)

@admin_bp.route('/user/<int:user_id>/view')
@admin_required
def view_user(user_id):
    user = User.query.get_or_404(user_id)
    # Get all scores for this user
    scores = Score.query.filter_by(user_id=user_id).order_by(Score.attempt_date.desc()).all()
    
    # Calculate statistics
    total_quizzes = len(scores)
    if total_quizzes > 0:
        average_score = sum(score.score / score.total_questions * 100 for score in scores) / total_quizzes
    else:
        average_score = 0
    
    return render_template('admin/user_profile.html', user=user, scores=scores,
                        total_quizzes=total_quizzes, average_score=average_score)

# Add this route for testing - this makes a quiz available immediately
@admin_bp.route('/quiz/<int:quiz_id>/make-available')
@admin_required
def make_quiz_available(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Set quiz date to 1 hour ago
    quiz.date_of_quiz = datetime.utcnow() - timedelta(hours=1)
    
    db.session.commit()
    flash(f'Quiz "{quiz.chapter.name}" is now available for immediate access')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/subject/new', methods=['GET', 'POST'])
@admin_required
def new_subject():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        subject = Subject(name=name, description=description)
        db.session.add(subject)
        db.session.commit()
        
        flash('Subject created successfully')
        return redirect(url_for('admin.dashboard'))
    
    return render_template('admin/subject_form.html')

@admin_bp.route('/subject/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_subject(id):
    subject = Subject.query.get_or_404(id)
    
    if request.method == 'POST':
        subject.name = request.form.get('name')
        subject.description = request.form.get('description')
        db.session.commit()
        
        flash('Subject updated successfully')
        return redirect(url_for('admin.dashboard'))
    
    return render_template('admin/subject_form.html', subject=subject)

@admin_bp.route('/subject/<int:id>/delete')
@admin_required
def delete_subject(id):
    subject = Subject.query.get_or_404(id)
    db.session.delete(subject)
    db.session.commit()
    
    flash('Subject deleted successfully')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/chapter/<int:id>/delete')
@admin_required
def delete_chapter(id):
    chapter = Chapter.query.get_or_404(id)
    db.session.delete(chapter)
    db.session.commit()
    
    flash('Chapter deleted successfully')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/subject/<int:subject_id>/chapter/new', methods=['GET', 'POST'])
@admin_required
def new_chapter(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        chapter = Chapter(name=name, description=description, subject=subject)
        db.session.add(chapter)
        db.session.commit()
        
        flash('Chapter created successfully')
        return redirect(url_for('admin.dashboard'))
    
    return render_template('admin/chapter_form.html', subject=subject)

@admin_bp.route('/chapter/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_chapter(id):
    chapter = Chapter.query.get_or_404(id)
    
    if request.method == 'POST':
        chapter.name = request.form.get('name')
        chapter.description = request.form.get('description')
        db.session.commit()
        
        flash('Chapter updated successfully')
        return redirect(url_for('admin.dashboard'))
    
    return render_template('admin/chapter_edit.html', chapter=chapter)

@admin_bp.route('/chapter/<int:id>/quiz/new', methods=['GET', 'POST'])
@admin_required
def new_quiz(id):
    chapter = Chapter.query.get_or_404(id)
    
    if request.method == 'POST':
        date_str = request.form.get('date_of_quiz')
        duration = int(request.form.get('duration'))
        remarks = request.form.get('remarks')
        
        quiz = Quiz(
            chapter=chapter,
            date_of_quiz=datetime.strptime(date_str, '%Y-%m-%dT%H:%M'),
            duration=duration,
            remarks=remarks
        )
        db.session.add(quiz)
        db.session.commit()
        
        flash('Quiz created successfully')
        return redirect(url_for('admin.add_questions', quiz_id=quiz.id))
    
    return render_template('admin/quiz_form.html', chapter=chapter)

@admin_bp.route('/quiz/<int:quiz_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    
    if request.method == 'POST':
        date_str = request.form.get('date_of_quiz')
        duration = int(request.form.get('duration'))
        remarks = request.form.get('remarks')
        
        quiz.date_of_quiz = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        quiz.duration = duration
        quiz.remarks = remarks
        
        db.session.commit()
        
        flash('Quiz updated successfully')
        return redirect(url_for('admin.dashboard'))
    
    return render_template('admin/quiz_edit.html', quiz=quiz)

@admin_bp.route('/quiz/<int:quiz_id>/delete')
@admin_required
def delete_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    db.session.delete(quiz)
    db.session.commit()
    
    flash('Quiz deleted successfully')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/quiz/<int:quiz_id>/questions', methods=['GET', 'POST'])
@admin_required
def add_questions(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    
    if request.method == 'POST':
        question_text = request.form.get('question_text')
        options = [
            request.form.get(f'option_{i}')
            for i in range(1, 5)
        ]
        correct_option = int(request.form.get('correct_option'))
        
        question = Question(
            quiz=quiz,
            question_text=question_text,
            option_1=options[0],
            option_2=options[1],
            option_3=options[2],
            option_4=options[3],
            correct_option=correct_option
        )
        db.session.add(question)
        db.session.commit()
        
        if 'add_another' in request.form:
            flash('Question added successfully')
            return redirect(url_for('admin.add_questions', quiz_id=quiz.id))
        
        flash('Quiz questions completed')
        return redirect(url_for('admin.dashboard'))
    
    return render_template('admin/question_form.html', quiz=quiz)

@admin_bp.route('/quiz/<int:quiz_id>/manage-questions')
@admin_required
def manage_questions(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    return render_template('admin/manage_questions.html', quiz=quiz)

@admin_bp.route('/question/<int:question_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_question(question_id):
    question = Question.query.get_or_404(question_id)
    
    if request.method == 'POST':
        question.question_text = request.form.get('question_text')
        question.option_1 = request.form.get('option_1')
        question.option_2 = request.form.get('option_2')
        question.option_3 = request.form.get('option_3')
        question.option_4 = request.form.get('option_4')
        question.correct_option = int(request.form.get('correct_option'))
        
        db.session.commit()
        
        flash('Question updated successfully')
        return redirect(url_for('admin.manage_questions', quiz_id=question.quiz_id))
    
    return render_template('admin/question_edit.html', question=question)

@admin_bp.route('/question/<int:question_id>/delete')
@admin_required
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    quiz_id = question.quiz_id
    
    db.session.delete(question)
    db.session.commit()
    
    flash('Question deleted successfully')
    return redirect(url_for('admin.manage_questions', quiz_id=quiz_id))

@admin_bp.route('/stats')
@admin_required
def stats():
    # Gather statistics
    stats = {
        'users': {
            'total': User.query.filter_by(is_admin=False).count(),
            'recent': User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).limit(5).all()
        },
        'subjects': {
            'total': Subject.query.count(),
            'by_chapters': []
        },
        'quizzes': {
            'total': Quiz.query.count(),
            'recent': Quiz.query.order_by(Quiz.created_at.desc()).limit(5).all(),
            'most_questions': Quiz.query.outerjoin(Quiz.questions).group_by(Quiz.id)
                .order_by(db.func.count(Question.id).desc()).limit(5).all()
        },
        'questions': {
            'total': Question.query.count()
        },
        'scores': {
            'total': Score.query.count(),
            'average': db.session.query(db.func.avg(Score.score * 100 / Score.total_questions)).scalar() or 0,
            'recent': Score.query.order_by(Score.attempt_date.desc()).limit(5).all()
        }
    }
    
    # Get subjects with chapter counts for pie chart
    subjects = Subject.query.all()
    for subject in subjects:
        stats['subjects']['by_chapters'].append({
            'name': subject.name,
            'chapter_count': len(subject.chapters)
        })
    
    # Get quiz counts per subject for another chart
    quizzes_by_subject = []
    for subject in subjects:
        quiz_count = 0
        for chapter in subject.chapters:
            quiz_count += len(chapter.quizzes)
        
        quizzes_by_subject.append({
            'name': subject.name,
            'quiz_count': quiz_count
        })
    
    # Get user quiz attempt stats
    user_attempts = db.session.query(
        User.id, User.full_name, db.func.count(Score.id).label('attempt_count')
    ).join(Score).filter(User.is_admin == False).group_by(User.id).order_by(
        db.desc('attempt_count')
    ).limit(5).all()
    
    # Prepare data for charts
    chart_data = {
        'subjects': {
            'labels': [subject['name'] for subject in stats['subjects']['by_chapters']],
            'data': [subject['chapter_count'] for subject in stats['subjects']['by_chapters']]
        },
        'quizzes': {
            'labels': [subject['name'] for subject in quizzes_by_subject],
            'data': [subject['quiz_count'] for subject in quizzes_by_subject]
        },
        'users': {
            'labels': [user[1] for user in user_attempts],
            'data': [user[2] for user in user_attempts]
        }
    }
    
    return render_template('admin/stats.html', stats=stats, chart_data=chart_data) 