from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models.quiz import Subject, Quiz, Question, Score
from app import db
from datetime import datetime, timedelta
from sqlalchemy import or_

user_bp = Blueprint('user', __name__, url_prefix='/user')

@user_bp.route('/')
@login_required
def dashboard():
    subjects = Subject.query.all()
    
    # Get current time
    current_time = datetime.utcnow()
    
    # For debugging - print to console
    print(f"Current time (UTC): {current_time}")
    
    # Get upcoming quizzes AND available quizzes that the user hasn't taken yet
    quizzes = Quiz.query.filter(
        # Get quizzes that haven't been taken by this user
        ~Quiz.id.in_(
            db.session.query(Score.quiz_id).filter_by(user_id=current_user.id)
        )
    ).all()
    
    # Sort quizzes into upcoming and available
    upcoming_quizzes = []
    available_quizzes = []
    
    for quiz in quizzes:
        # Print quiz info for debugging
        print(f"Quiz ID: {quiz.id}, Date: {quiz.date_of_quiz}, Current: {current_time}")
        print(f"Quiz timestamp: {quiz.date_of_quiz.timestamp()}, Current timestamp: {current_time.timestamp()}")
        print(f"Is quiz in future? {current_time.timestamp() < quiz.date_of_quiz.timestamp()}")
        
        # If the quiz is in the future
        if current_time.timestamp() < quiz.date_of_quiz.timestamp():
            upcoming_quizzes.append(quiz)
        else:
            # The quiz is in the past or current (available)
            available_quizzes.append(quiz)
    
    # Get completed quizzes
    completed_quizzes = Score.query.filter_by(user_id=current_user.id).all()
    
    return render_template('user/dashboard.html', 
                         subjects=subjects, 
                         upcoming_quizzes=upcoming_quizzes,
                         available_quizzes=available_quizzes,
                         completed_quizzes=completed_quizzes)

@user_bp.route('/quiz/<int:quiz_id>')
@login_required
def view_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Check if quiz is already taken
    if Score.query.filter_by(user_id=current_user.id, quiz_id=quiz_id).first():
        flash('You have already taken this quiz')
        return redirect(url_for('user.dashboard'))
    
    # DEBUGGING: Get the current time and quiz time
    current_time = datetime.utcnow()
    quiz_time = quiz.date_of_quiz
    
    print(f"Current time (UTC): {current_time}")
    print(f"Quiz time: {quiz_time}")
    print(f"Current timestamp: {current_time.timestamp()}")
    print(f"Quiz timestamp: {quiz_time.timestamp()}")
    print(f"Is quiz in future? {current_time.timestamp() < quiz_time.timestamp()}")
    
    # For TESTING: Override current_time to simulate a date in the future
    # Remove/comment this line in production
    # current_time = datetime(2025, 4, 1, 12, 0, 0)  # A date after the quiz date
    
    # Check if quiz is available - using timestamp to avoid timezone issues
    if current_time.timestamp() < quiz.date_of_quiz.timestamp():
        flash('This quiz is not yet available')
        return redirect(url_for('user.dashboard'))
    
    return render_template('user/quiz_start.html', quiz=quiz)

@user_bp.route('/quiz/<int:quiz_id>/take', methods=['GET', 'POST'])
@login_required
def take_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Check if quiz is already taken
    if Score.query.filter_by(user_id=current_user.id, quiz_id=quiz_id).first():
        flash('You have already taken this quiz')
        return redirect(url_for('user.dashboard'))
    
    # Check if quiz is available before allowing the user to take it
    current_time = datetime.utcnow()
    
    # For TESTING: Override current_time to simulate a date in the future
    # Remove/comment this line in production  
    # current_time = datetime(2025, 4, 1, 12, 0, 0)  # A date after the quiz date
    
    if current_time.timestamp() < quiz.date_of_quiz.timestamp():
        flash('This quiz is not yet available')
        return redirect(url_for('user.dashboard'))
    
    if request.method == 'POST':
        score = 0
        for question in quiz.questions:
            selected_option = request.form.get(f'question_{question.id}')
            if selected_option and int(selected_option) == question.correct_option:
                score += 1
        
        # Record the score
        quiz_score = Score(
            user=current_user,
            quiz=quiz,
            score=score,
            total_questions=len(quiz.questions),
            completion_time=quiz.duration  # Assuming they took the full time
        )
        db.session.add(quiz_score)
        db.session.commit()
        
        flash(f'Quiz completed! Your score: {score}/{len(quiz.questions)}')
        return redirect(url_for('user.view_score', score_id=quiz_score.id))
    
    return render_template('user/quiz_take.html', quiz=quiz)

@user_bp.route('/score/<int:score_id>')
@login_required
def view_score(score_id):
    score = Score.query.get_or_404(score_id)
    if score.user_id != current_user.id:
        flash('Access denied')
        return redirect(url_for('user.dashboard'))
    
    return render_template('user/score.html', score=score)

@user_bp.route('/scores')
@login_required
def view_scores():
    # Get all scores for the current user, ordered by attempt date
    scores = Score.query.filter_by(user_id=current_user.id)\
        .order_by(Score.attempt_date.desc())\
        .all()
    
    # Calculate statistics
    total_quizzes = len(scores)
    if total_quizzes > 0:
        average_score = sum(score.score / score.total_questions * 100 for score in scores) / total_quizzes
    else:
        average_score = 0
    
    return render_template('user/scores.html', 
                         scores=scores,
                         total_quizzes=total_quizzes,
                         average_score=average_score) 