from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysqldb import MySQL
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = ' '

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'health_tracker'

mysql = MySQL(app)

@app.route('/', methods=['GET'])
def index():
    cur = mysql.connection.cursor()
    
    # Bugünün verileri
    today = datetime.now().date()
    today_start = today.strftime('%Y-%m-%d 00:00:00')
    today_end = today.strftime('%Y-%m-%d 23:59:59')
    
    cur.execute("""
        SELECT * FROM tracker_entries 
        WHERE date BETWEEN %s AND %s 
        ORDER BY date DESC
    """, (today_start, today_end))
    today_data = cur.fetchall()

    # Son 7 günün verileri
    week_start = (today - timedelta(days=6)).strftime('%Y-%m-%d 00:00:00')
    cur.execute("""
        SELECT date, entry_type, details 
        FROM tracker_entries 
        WHERE date BETWEEN %s AND %s
    """, (week_start, today_end))
    weekly_data = cur.fetchall()

    # Hedef verisi
    cur.execute("SELECT * FROM goals ORDER BY id DESC LIMIT 1")
    goal = cur.fetchone()
    cur.close()

    # Haftalık istatistikleri hesapla
    weekly_stats = process_weekly_data(weekly_data)
    goal_status = check_goals(goal, today_data)

    return render_template('index.html', 
                         data=today_data, 
                         goal=goal, 
                         goal_status=goal_status,
                         weekly_stats=weekly_stats)

def process_weekly_data(weekly_data):
    # Son 7 günün tarihlerini oluştur
    dates = [(datetime.now().date() - timedelta(days=x)).strftime('%d/%m') 
             for x in range(6, -1, -1)]
    
    stats = {
        'dates': dates,
        'water': [0] * 7,
        'calories': [0] * 7,
        'activity': [0] * 7
    }
    
    for entry in weekly_data:
        date = entry[0].strftime('%d/%m')
        if date in dates:
            day_index = dates.index(date)
            entry_type = entry[1]
            details = entry[2]
            
            try:
                if entry_type == 'Water':
                    water_amount = float(details.split()[0])
                    stats['water'][day_index] += water_amount
                elif entry_type == 'Meal':
                    calories = int(details.split('-')[1].strip().split()[0])
                    stats['calories'][day_index] += calories
                elif entry_type == 'Activity':
                    activity_calories = int(details.split('-')[1].strip().split()[0])
                    stats['activity'][day_index] += activity_calories
            except (ValueError, IndexError):
                continue
    
    return stats

def check_goals(goal, data):
    goal_status = {
        'water': 'green',
        'meal': 'green',
        'activity': 'green',
        'water_percentage': 0, 
        'meal_percentage': 0,  
        'activity_percentage': 0,
        'water_total': 0,
        'meal_total': 0,
        'activity_total': 0
    }

    if goal and data:  # Hem hedef hem de bugünün verisi varsa
        try:
            water_goal = float(goal[1]) if goal[1] else 0
            meal_goal = int(goal[2]) if goal[2] else 0
            activity_goal = int(goal[3]) if goal[3] else 0

            # Sadece bugünün verilerini topla
            total_water = sum([float(entry[3].split()[0]) for entry in data if entry[2] == 'Water'])
            goal_status['water_total'] = total_water
            water_percentage = (total_water / water_goal * 100) if water_goal > 0 else 0
            goal_status['water_percentage'] = min(water_percentage, 100)
            goal_status['water'] = 'red' if total_water < water_goal else 'green'

            total_meal = sum([int(entry[3].split('-')[1].strip().split()[0]) for entry in data if entry[2] == 'Meal'])
            goal_status['meal_total'] = total_meal
            meal_percentage = (total_meal / meal_goal * 100) if meal_goal > 0 else 0
            goal_status['meal_percentage'] = min(meal_percentage, 100)
            goal_status['meal'] = 'red' if total_meal > meal_goal else 'green'

            total_activity = sum([int(entry[3].split('-')[1].strip().split()[0]) for entry in data if entry[2] == 'Activity'])
            goal_status['activity_total'] = total_activity
            activity_percentage = (total_activity / activity_goal * 100) if activity_goal > 0 else 0
            goal_status['activity_percentage'] = min(activity_percentage, 100)
            goal_status['activity'] = 'red' if total_activity < activity_goal else 'green'

        except (IndexError, ValueError, TypeError) as e:
            print(f"Hedef hesaplama hatası: {str(e)}")

    return goal_status

@app.route('/track_water', methods=['POST'])
def track_water():
    try:
        water_amount = float(request.form['water_amount']) 
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO tracker_entries (entry_type, date, details) VALUES (%s, %s, %s)", 
                   ('Water', date, f'{water_amount} liters'))
        mysql.connection.commit()
        cur.close()

        flash('Su eklendi!', 'success')
    except Exception as e:
        flash('Hata oluştu!', 'error')
        print(f"Hata: {str(e)}")
    
    return redirect(url_for('index'))

# Yemek takibi (Modal)
@app.route('/track_meals', methods=['POST'])
def track_meals():
    meal_name = request.form['meal_name']
    calories = request.form['calories']
    date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO tracker_entries (entry_type, date, details) VALUES (%s, %s, %s)", ('Meal', date, f'{meal_name} - {calories} calories'))
    mysql.connection.commit()
    cur.close()

    flash('Meal tracked successfully!', 'success')
    return redirect(url_for('index'))


@app.route('/track_activities', methods=['POST'])
def track_activities():
    try:
        activity_type = request.form['activity_type'] 
        duration = request.form['duration']
        calories_burned = request.form['calories_burned']
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        activity_details = f"{activity_type} - {calories_burned} calories"

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO tracker_entries (entry_type, date, details) VALUES (%s, %s, %s)", 
                   ('Activity', date, activity_details))
        mysql.connection.commit()
        cur.close()

        flash('Aktivite başarıyla eklendi!', 'success')
    except Exception as e:
        flash('Hata oluştu!', 'error')
        print(f"Hata: {str(e)}")
    
    return redirect(url_for('index'))


# Hedef belirleme (Modal)
@app.route('/set_goal', methods=['GET', 'POST'])
def set_goal():
    if request.method == 'POST':
        water_goal = request.form['water_goal']
        meal_goal = request.form['meal_goal']
        activity_goal = request.form['activity_goal']

        cur = mysql.connection.cursor()
        
        # mevcut hedef kontrolü
        cur.execute("SELECT * FROM goals ORDER BY id DESC LIMIT 1")
        existing_goal = cur.fetchone()
        
        if existing_goal:
            cur.execute("""
                UPDATE goals 
                SET water_goal = %s, meal_goal = %s, activity_goal = %s 
                WHERE id = %s
            """, (water_goal, meal_goal, activity_goal, existing_goal[0]))
        else:
            # yoksa yeni ekle
            cur.execute("""
                INSERT INTO goals (water_goal, meal_goal, activity_goal) 
                VALUES (%s, %s, %s)
            """, (water_goal, meal_goal, activity_goal))
            
        mysql.connection.commit()
        cur.close()
        
        flash('Hedefleriniz başarıyla güncellendi!', 'success')
        return redirect(url_for('index'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM goals ORDER BY id DESC LIMIT 1")
    goal = cur.fetchone()
    cur.close()

    return render_template('set_goal.html', goal=goal)

if __name__ == '__main__':
    app.run(debug=True)
