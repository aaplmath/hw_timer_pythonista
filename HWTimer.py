import ui
import datetime
import sqlite3
import console
from matplotlib import pyplot as plt, dates as mdates
import matplotlib as mpl
from io import BytesIO
import numpy as np

db_path = 'db/hwtimer.db'

del_tmp = 'DELETE FROM tmp_save'

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute('''CREATE TABLE IF NOT EXISTS entries (
        id integer primary key,
        subject text NOT NULL,
        day date NOT NULL,
        time integer NOT NULL)''')
cur.execute('''CREATE TABLE IF NOT EXISTS tmp_save (
    id integer primary key,
    subject text NOT NULL,
    start_time date NOT NULL)''')
conn.commit()

start_time = None


def subject_selected(sender):
    '@type sender ui.ListDataSource'
    initiate_timer(sender.items[sender.selected_row], datetime.datetime.now(), True)
    

def initiate_timer(subj, init_time, create_save):
    global tv, start_time, curr_subj
    tv.touch_enabled = False
    start_time = init_time
    curr_subj = subj
    button.background_color = (1, 0, 0, 1)
    if create_save:
        tmp_con = sqlite3.connect(db_path)
        tmp_con.cursor().execute('INSERT INTO tmp_save VALUES (NULL, "{}", datetime("{}"))'.format(curr_subj, start_time))
        tmp_con.commit()
        tmp_con.close()
    

def stop_pressed(sender):
    '@type sender ui.Button'
    global start_time
    if start_time is not None:
        total_time = datetime.datetime.now() - start_time
        tv.touch_enabled = True
        tv.selected_rows = ()
        start_time = None
        button.background_color = (0.5, 0.5, 0.5, 1)
        if total_time.total_seconds() < 10:
            alert_too_short()
            loc_con = sqlite3.connect(db_path)
            loc_con.execute(del_tmp)
            loc_con.commit()
            return
        
        insert_query = 'INSERT INTO entries VALUES (NULL, "{0}", date("{1}"), {2})'.format(curr_subj, datetime.date.today(), round(total_time.total_seconds()))
        loc_con = sqlite3.connect(db_path)
        loc_con.cursor().execute(insert_query)
        loc_con.execute(del_tmp)
        loc_con.commit()


@ui.in_background
def alert_too_short():
    console.alert('Time interval too short—session not saved')


@ui.in_background
def add_manual(sender):
    add_subject = console.input_alert('Subject Name:')
    if add_subject != '':
        add_seconds = console.input_alert('Seconds Spent:')
        if add_seconds != '':
            add_query = 'INSERT INTO entries VALUES (null, "{0}", date("{1}"), {2})'.format(add_subject, datetime.date.today(), add_seconds)
            add_con = sqlite3.connect(db_path)
            add_con.cursor().execute(add_query)
            add_con.commit()


def show_graph(sender):
    # graph styles and labels
    mpl.style.use('bmh')
    plt.title('HW Time Spent')
    plt.xlabel('Date')
    plt.ylabel('Minutes spent')
    plt.grid(linestyle='dashed')
    
    # set up date axis and plot raw data
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%d/%y'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=15))
    plt.plot(g_dates, g_data, '#fa4224', linewidth=0.5)
    
    # hacky "smoothing" (https://stackoverflow.com/a/26337730)
    smooth_box_pts = np.round(np.log2(len(g_data))) + 1  # number of days to aggregate when smoothing
    box = np.ones(smooth_box_pts)/smooth_box_pts
    y_smooth = np.convolve(g_data, box, mode='same')
    plt.plot(g_dates, y_smooth, 'g-', linewidth=2.0)
    
    # make y-axis start at 0
    plt.axes().set_ylim(0, plt.axes().get_ylim()[1])
    
    # make date labels fit
    plt.gcf().autofmt_xdate()
    
    bytes = BytesIO()
    plt.savefig(bytes)
    img = ui.Image.from_data(bytes.getvalue())
    img_view = ui.ImageView(background_color='white')
    img_view.content_mode = ui.CONTENT_SCALE_ASPECT_FIT
    img_view.image = img
    img_view.present()
    plt.clf()


def load_entries(sender):
    global g_data, g_dates
    load_con = sqlite3.connect(db_path)
    day_entries = load_con.cursor().execute('SELECT subject, day, sum(time) FROM entries GROUP BY day, subject ORDER BY subject, day')
    
    # Set up full list
    entries = {}
    all_data = ''
    for entry in day_entries:
        if entry[0] in entries:
            entries[entry[0]]['sum'] += entry[2]
            entries[entry[0]]['days'] += 1
        else:
            entries[entry[0]] = {
                'sum': entry[2],
                'days': 1
            }
        all_data += '{}, {}: {} mins\n'.format(entry[0], entry[1], round(entry[2] / 60, 2))
    
    # Set up averages
    disp = ''
    for subj in entries:
        disp += '{}: {} min/day ({} total)\n'.format(subj,
        round(entries[subj]['sum'] / entries[subj]['days'] / 60, 2),
        round(entries[subj]['sum'] / 60))
    disp = disp[:-1]
    
    # Set up day sums
    day_sums = load_con.cursor().execute('SELECT day, sum(time) FROM entries GROUP BY day ORDER BY day DESC')
    total_title = 'TOTALS:'
    total_sum = 0
    count = 0
    g_data = []
    g_dates = []
    day_text = ''
    for sum_entry in day_sums:
        day_text += '{}: {} mins\n'.format(sum_entry[0], round(sum_entry[1] / 60, 2))
        
        g_data.append(sum_entry[1] / 60)
        g_dates.append(datetime.datetime.strptime(sum_entry[0], '%Y-%m-%d').date())
        
        total_sum += sum_entry[1]
        count += 1
    # Avoid divide-by-zero errors
    if count == 0:
        avg = 0
    else:
        avg = round(total_sum / count / 60, 2)
    avg_text = 'AVG: {} mins'.format(avg)
    total_text = f'{total_title}\n\n{avg_text}\n\n{day_text}'
    # Add views
    v = ui.View()
    
    label = ui.TextView(height=200, width=500)
    label.text = 'SUBJECT AVERAGES:\n\n' + disp
    label.editable = False
    v.add_subview(label)
    
    label2 = ui.TextView(height=600, width=500, y=120)
    label2.text = 'ALL DATA:\n\n' + all_data
    label2.editable = False
    v.add_subview(label2)
    
    label_days = ui.TextView(height=650, width=200, x=200)
    label_days.text = total_text
    label_days.editable = False
    v.add_subview(label_days)
    
    graph_button = ui.Button(height=20, width=50, x=250, y=670)
    graph_button.title = 'Graph'
    # Avoid errors by disallowing graphing with an empty DB
    if count == 0:
        graph_button.enabled = False
    else:
        graph_button.action = show_graph
    v.add_subview(graph_button)
    
    v.present('sheet')
    load_con.close()
    
def main():
    global tv, button
    v = ui.load_view()
    v.present('fullscreen')
    tv = v.subviews[0]
    button = v.subviews[1]
    save = cur.execute('SELECT subject, start_time FROM tmp_save').fetchone()
    conn.commit()
    if save is not None:
        select = console.alert('Save Exists', 'There is an unfinished session in progress:\nSubject: {}\nStart Time: {}'.format(save[0], save[1]), 'Discard', 'Resume')
        if select == 1:
            cur.execute(del_tmp)
            conn.commit()
            conn.close()
        elif select == 2:
            # Don't del temp because we might want that save if this session unexpectedly terminates, too; similarly, don't create another save because this one already exists
            conn.close()
            initiate_timer(save[0], datetime.datetime.strptime(save[1], '%Y-%m-%d %H:%M:%S'), False)
        else:
            conn.close()
    else:
        conn.close()

if __name__ == "__main__":
    main()
