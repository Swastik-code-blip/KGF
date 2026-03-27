from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import pandas as pd
import io
import os

app = Flask(__name__)
app.secret_key = 'kgf-portal-secret-key-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kgf_portal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ─── MODELS ───────────────────────────────────────────────────────────────────

class User(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role     = db.Column(db.String(20), nullable=False)  # admin / leader / agent
    name     = db.Column(db.String(120))
    created  = db.Column(db.DateTime, default=datetime.utcnow)

class Activation(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    kgf_serial       = db.Column(db.Integer)
    kgf_id           = db.Column(db.String(20))
    member_name      = db.Column(db.String(120))
    amount           = db.Column(db.Float)
    topup_amount     = db.Column(db.Float)
    avail_balance    = db.Column(db.Float)
    contact          = db.Column(db.String(20))
    state            = db.Column(db.String(50))
    dist             = db.Column(db.String(50))
    status           = db.Column(db.String(30))
    payments         = db.Column(db.String(50))
    leader_name      = db.Column(db.String(100))
    date             = db.Column(db.Date)
    remark           = db.Column(db.String(200))
    utr_no           = db.Column(db.String(200))
    pay_confirm_by   = db.Column(db.String(100))
    payment_date     = db.Column(db.String(50))
    created_by       = db.Column(db.String(80))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

class Cheque(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    member_name      = db.Column(db.String(120))
    contact          = db.Column(db.String(20))
    kgf_id           = db.Column(db.String(20))
    state            = db.Column(db.String(50))
    dist             = db.Column(db.String(50))
    cheque_status    = db.Column(db.String(30))
    cheque_no        = db.Column(db.String(50))
    cheque_date      = db.Column(db.String(30))
    due_date         = db.Column(db.String(30))
    package          = db.Column(db.String(50))
    agreement_status = db.Column(db.String(30))
    remarks          = db.Column(db.String(200))
    created_by       = db.Column(db.String(80))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

class Payout(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    benf_name   = db.Column(db.String(120))
    acc_no      = db.Column(db.String(30))
    ifsc        = db.Column(db.String(20))
    amount      = db.Column(db.Float)
    userid      = db.Column(db.String(20))
    pymt_date   = db.Column(db.String(30))
    bank        = db.Column(db.String(50))
    status      = db.Column(db.String(30))
    utr         = db.Column(db.String(50))
    remarks     = db.Column(db.String(200))
    created_by  = db.Column(db.String(80))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

class Query(db.Model):
    id                = db.Column(db.Integer, primary_key=True)
    member_name       = db.Column(db.String(120))
    contact           = db.Column(db.String(20))
    state             = db.Column(db.String(50))
    dist              = db.Column(db.String(50))
    date              = db.Column(db.String(30))
    query_type        = db.Column(db.String(50))
    call_attender     = db.Column(db.String(100))
    department        = db.Column(db.String(50))
    remarks           = db.Column(db.String(200))
    status            = db.Column(db.String(20), default='open')
    followup1         = db.Column(db.String(200))
    followup2         = db.Column(db.String(200))
    followup3         = db.Column(db.String(200))
    created_by        = db.Column(db.String(80))
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

# ─── AUTH HELPERS ──────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('role') not in roles:
                flash('Access denied / अनुमति नहीं है', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator

# ─── AUTH ROUTES ──────────────────────────────────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form['username']).first()
        if u and check_password_hash(u.password, request.form['password']):
            session['user_id'] = u.id
            session['username'] = u.username
            session['role'] = u.role
            session['name'] = u.name
            return redirect(url_for('dashboard'))
        flash('Invalid credentials / गलत username या password', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    stats = {
        'total_activations': Activation.query.count(),
        'done':              Activation.query.filter_by(status='DONE').count(),
        'pending':           Activation.query.filter(Activation.status.notin_(['DONE'])).count(),
        'total_cheques':     Cheque.query.count(),
        'total_payouts':     Payout.query.count(),
        'open_queries':      Query.query.filter_by(status='open').count(),
        'closed_queries':    Query.query.filter_by(status='close').count(),
    }
    recent = Activation.query.order_by(Activation.created_at.desc()).limit(5).all()
    return render_template('dashboard.html', stats=stats, recent=recent)

# ─── ACTIVATIONS ──────────────────────────────────────────────────────────────

@app.route('/activations')
@login_required
def activations():
    q      = request.args.get('q', '')
    status = request.args.get('status', '')
    state  = request.args.get('state', '')
    query  = Activation.query
    if q:
        query = query.filter(
            db.or_(Activation.kgf_id.ilike(f'%{q}%'),
                   Activation.member_name.ilike(f'%{q}%'),
                   Activation.contact.ilike(f'%{q}%')))
    if status:
        query = query.filter_by(status=status)
    if state:
        query = query.filter_by(state=state)
    records = query.order_by(Activation.id.desc()).all()
    states  = db.session.query(Activation.state).distinct().all()
    return render_template('activations.html', records=records,
                           q=q, status=status, state=state,
                           states=[s[0] for s in states if s[0]])

@app.route('/activations/add', methods=['GET', 'POST'])
@login_required
def add_activation():
    if request.method == 'POST':
        f = request.form
        rec = Activation(
            kgf_serial=f.get('kgf_serial') or None,
            kgf_id=f['kgf_id'], member_name=f['member_name'],
            amount=f.get('amount') or 0, topup_amount=f.get('topup_amount') or 0,
            avail_balance=f.get('avail_balance') or 0,
            contact=f['contact'], state=f['state'], dist=f.get('dist'),
            status=f['status'], payments=f.get('payments'),
            leader_name=f.get('leader_name'), remark=f.get('remark'),
            utr_no=f.get('utr_no'), pay_confirm_by=f.get('pay_confirm_by'),
            payment_date=f.get('payment_date'),
            date=datetime.strptime(f['date'], '%Y-%m-%d').date() if f.get('date') else None,
            created_by=session['username'])
        db.session.add(rec)
        db.session.commit()
        flash('Record added / रिकॉर्ड जोड़ा गया ✓', 'success')
        return redirect(url_for('activations'))
    return render_template('activation_form.html', rec=None)

@app.route('/activations/edit/<int:rid>', methods=['GET', 'POST'])
@login_required
def edit_activation(rid):
    rec = Activation.query.get_or_404(rid)
    if request.method == 'POST':
        f = request.form
        rec.kgf_id=f['kgf_id']; rec.member_name=f['member_name']
        rec.amount=f.get('amount') or 0; rec.topup_amount=f.get('topup_amount') or 0
        rec.avail_balance=f.get('avail_balance') or 0
        rec.contact=f['contact']; rec.state=f['state']; rec.dist=f.get('dist')
        rec.status=f['status']; rec.payments=f.get('payments')
        rec.leader_name=f.get('leader_name'); rec.remark=f.get('remark')
        rec.utr_no=f.get('utr_no'); rec.pay_confirm_by=f.get('pay_confirm_by')
        rec.payment_date=f.get('payment_date')
        rec.date=datetime.strptime(f['date'], '%Y-%m-%d').date() if f.get('date') else None
        db.session.commit()
        flash('Record updated / अपडेट हो गया ✓', 'success')
        return redirect(url_for('activations'))
    return render_template('activation_form.html', rec=rec)

@app.route('/activations/delete/<int:rid>', methods=['POST'])
@login_required
@role_required('admin')
def delete_activation(rid):
    db.session.delete(Activation.query.get_or_404(rid))
    db.session.commit()
    flash('Deleted / हटाया गया', 'warning')
    return redirect(url_for('activations'))

@app.route('/activations/import', methods=['POST'])
@login_required
@role_required('admin')
def import_activations():
    f = request.files.get('file')
    if not f:
        flash('No file / फाइल नहीं मिली', 'danger')
        return redirect(url_for('activations'))
    df = pd.read_excel(f, sheet_name='ID ACTIVATION')
    df.columns = [str(c).strip() for c in df.columns]
    count = 0
    for _, row in df.iterrows():
        if pd.isna(row.get('ID')): continue
        rec = Activation(
            kgf_serial=row.get('kgf'), kgf_id=str(row.get('ID','')),
            member_name=str(row.get('Name','')),
            amount=row.get('Amount') if pd.notna(row.get('Amount')) else 0,
            topup_amount=row.get('Topup Amount') if pd.notna(row.get('Topup Amount')) else 0,
            avail_balance=row.get('AVAILABLE BALANCE') if pd.notna(row.get('AVAILABLE BALANCE')) else 0,
            contact=str(row.get('Contact NO','')),
            state=str(row.get('STATE','')) if pd.notna(row.get('STATE')) else '',
            dist=str(row.get('Dist','')) if pd.notna(row.get('Dist')) else '',
            status=str(row.get('STATUS','')) if pd.notna(row.get('STATUS')) else '',
            payments=str(row.get('PAYMENTS','')) if pd.notna(row.get('PAYMENTS')) else '',
            leader_name=str(row.get('LEADER NAME','')) if pd.notna(row.get('LEADER NAME')) else '',
            remark=str(row.get('REMARK','')) if pd.notna(row.get('REMARK')) else '',
            utr_no=str(row.get('UTR NO','')) if pd.notna(row.get('UTR NO')) else '',
            pay_confirm_by=str(row.get('PAY CONFIRM BY','')) if pd.notna(row.get('PAY CONFIRM BY')) else '',
            payment_date=str(row.get('PAYMENT DATE','')) if pd.notna(row.get('PAYMENT DATE')) else '',
            created_by='import')
        db.session.add(rec); count += 1
    db.session.commit()
    flash(f'{count} records imported / {count} रिकॉर्ड आयात हुए ✓', 'success')
    return redirect(url_for('activations'))

@app.route('/activations/export')
@login_required
def export_activations():
    records = Activation.query.all()
    data = [{
        'S.No': r.kgf_serial, 'KGF ID': r.kgf_id, 'Name': r.member_name,
        'Amount': r.amount, 'Topup': r.topup_amount, 'Balance': r.avail_balance,
        'Contact': r.contact, 'State': r.state, 'Dist': r.dist,
        'Status': r.status, 'Payment Mode': r.payments, 'Leader': r.leader_name,
        'Date': r.date, 'Remark': r.remark, 'UTR No': r.utr_no,
        'Confirmed By': r.pay_confirm_by, 'Payment Date': r.payment_date
    } for r in records]
    df = pd.DataFrame(data)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    return send_file(buf, download_name='activations_export.xlsx',
                     as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# ─── CHEQUE ───────────────────────────────────────────────────────────────────

@app.route('/cheques')
@login_required
def cheques():
    q      = request.args.get('q', '')
    status = request.args.get('status', '')
    query  = Cheque.query
    if q:
        query = query.filter(db.or_(Cheque.kgf_id.ilike(f'%{q}%'), Cheque.member_name.ilike(f'%{q}%')))
    if status:
        query = query.filter_by(cheque_status=status)
    records = query.order_by(Cheque.id.desc()).all()
    return render_template('cheques.html', records=records, q=q, status=status)

@app.route('/cheques/add', methods=['GET', 'POST'])
@login_required
def add_cheque():
    if request.method == 'POST':
        f = request.form
        rec = Cheque(member_name=f['member_name'], contact=f['contact'],
                     kgf_id=f['kgf_id'], state=f['state'], dist=f.get('dist'),
                     cheque_status=f['cheque_status'], cheque_no=f.get('cheque_no'),
                     cheque_date=f.get('cheque_date'), due_date=f.get('due_date'),
                     package=f.get('package'), agreement_status=f.get('agreement_status'),
                     remarks=f.get('remarks'), created_by=session['username'])
        db.session.add(rec); db.session.commit()
        flash('Cheque record added / चेक रिकॉर्ड जोड़ा गया ✓', 'success')
        return redirect(url_for('cheques'))
    return render_template('cheque_form.html', rec=None)

@app.route('/cheques/edit/<int:rid>', methods=['GET', 'POST'])
@login_required
def edit_cheque(rid):
    rec = Cheque.query.get_or_404(rid)
    if request.method == 'POST':
        f = request.form
        rec.member_name=f['member_name']; rec.contact=f['contact']
        rec.kgf_id=f['kgf_id']; rec.state=f['state']; rec.dist=f.get('dist')
        rec.cheque_status=f['cheque_status']; rec.cheque_no=f.get('cheque_no')
        rec.cheque_date=f.get('cheque_date'); rec.due_date=f.get('due_date')
        rec.package=f.get('package'); rec.agreement_status=f.get('agreement_status')
        rec.remarks=f.get('remarks')
        db.session.commit()
        flash('Updated / अपडेट हो गया ✓', 'success')
        return redirect(url_for('cheques'))
    return render_template('cheque_form.html', rec=rec)

@app.route('/cheques/export')
@login_required
def export_cheques():
    records = Cheque.query.all()
    data = [{'Name': r.member_name, 'Contact': r.contact, 'KGF ID': r.kgf_id,
              'State': r.state, 'Dist': r.dist, 'Cheque Status': r.cheque_status,
              'Cheque No': r.cheque_no, 'Cheque Date': r.cheque_date,
              'Due Date': r.due_date, 'Package': r.package,
              'Agreement Status': r.agreement_status, 'Remarks': r.remarks} for r in records]
    df = pd.DataFrame(data); buf = io.BytesIO()
    df.to_excel(buf, index=False); buf.seek(0)
    return send_file(buf, download_name='cheques_export.xlsx', as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# ─── PAYOUTS ──────────────────────────────────────────────────────────────────

@app.route('/payouts')
@login_required
def payouts():
    q      = request.args.get('q', '')
    status = request.args.get('status', '')
    query  = Payout.query
    if q:
        query = query.filter(db.or_(Payout.userid.ilike(f'%{q}%'), Payout.benf_name.ilike(f'%{q}%')))
    if status:
        query = query.filter_by(status=status)
    records = query.order_by(Payout.id.desc()).all()
    total   = sum(r.amount or 0 for r in records)
    return render_template('payouts.html', records=records, q=q, status=status, total=total)

@app.route('/payouts/add', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'leader')
def add_payout():
    if request.method == 'POST':
        f = request.form
        rec = Payout(benf_name=f['benf_name'], acc_no=f['acc_no'], ifsc=f['ifsc'],
                     amount=f.get('amount') or 0, userid=f['userid'],
                     pymt_date=f.get('pymt_date'), bank=f.get('bank'),
                     status=f.get('status','Pending'), utr=f.get('utr'),
                     remarks=f.get('remarks'), created_by=session['username'])
        db.session.add(rec); db.session.commit()
        flash('Payout added / पेआउट जोड़ा गया ✓', 'success')
        return redirect(url_for('payouts'))
    return render_template('payout_form.html', rec=None)

@app.route('/payouts/edit/<int:rid>', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'leader')
def edit_payout(rid):
    rec = Payout.query.get_or_404(rid)
    if request.method == 'POST':
        f = request.form
        rec.benf_name=f['benf_name']; rec.acc_no=f['acc_no']; rec.ifsc=f['ifsc']
        rec.amount=f.get('amount') or 0; rec.userid=f['userid']
        rec.pymt_date=f.get('pymt_date'); rec.bank=f.get('bank')
        rec.status=f.get('status','Pending'); rec.utr=f.get('utr'); rec.remarks=f.get('remarks')
        db.session.commit()
        flash('Updated / अपडेट हो गया ✓', 'success')
        return redirect(url_for('payouts'))
    return render_template('payout_form.html', rec=rec)

@app.route('/payouts/export')
@login_required
def export_payouts():
    records = Payout.query.all()
    data = [{'Name': r.benf_name, 'Account No': r.acc_no, 'IFSC': r.ifsc,
              'Amount': r.amount, 'User ID': r.userid, 'Payment Date': r.pymt_date,
              'Bank': r.bank, 'Status': r.status, 'UTR': r.utr, 'Remarks': r.remarks} for r in records]
    df = pd.DataFrame(data); buf = io.BytesIO()
    df.to_excel(buf, index=False); buf.seek(0)
    return send_file(buf, download_name='payouts_export.xlsx', as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# ─── QUERIES ──────────────────────────────────────────────────────────────────

@app.route('/queries')
@login_required
def queries():
    q      = request.args.get('q', '')
    status = request.args.get('status', '')
    query  = Query.query
    if q:
        query = query.filter(db.or_(Query.member_name.ilike(f'%{q}%'), Query.contact.ilike(f'%{q}%')))
    if status:
        query = query.filter_by(status=status)
    records = query.order_by(Query.id.desc()).all()
    return render_template('queries.html', records=records, q=q, status=status)

@app.route('/queries/add', methods=['GET', 'POST'])
@login_required
def add_query():
    if request.method == 'POST':
        f = request.form
        rec = Query(member_name=f['member_name'], contact=f['contact'],
                    state=f.get('state'), dist=f.get('dist'), date=f.get('date'),
                    query_type=f.get('query_type'), call_attender=f.get('call_attender'),
                    department=f.get('department'), remarks=f.get('remarks'),
                    status=f.get('status','open'), followup1=f.get('followup1'),
                    followup2=f.get('followup2'), followup3=f.get('followup3'),
                    created_by=session['username'])
        db.session.add(rec); db.session.commit()
        flash('Query logged / क्वेरी दर्ज हुई ✓', 'success')
        return redirect(url_for('queries'))
    return render_template('query_form.html', rec=None)

@app.route('/queries/edit/<int:rid>', methods=['GET', 'POST'])
@login_required
def edit_query(rid):
    rec = Query.query.get_or_404(rid)
    if request.method == 'POST':
        f = request.form
        rec.member_name=f['member_name']; rec.contact=f['contact']
        rec.state=f.get('state'); rec.dist=f.get('dist'); rec.date=f.get('date')
        rec.query_type=f.get('query_type'); rec.call_attender=f.get('call_attender')
        rec.department=f.get('department'); rec.remarks=f.get('remarks')
        rec.status=f.get('status','open'); rec.followup1=f.get('followup1')
        rec.followup2=f.get('followup2'); rec.followup3=f.get('followup3')
        db.session.commit()
        flash('Updated / अपडेट हो गया ✓', 'success')
        return redirect(url_for('queries'))
    return render_template('query_form.html', rec=rec)

@app.route('/queries/close/<int:rid>', methods=['POST'])
@login_required
def close_query(rid):
    rec = Query.query.get_or_404(rid)
    rec.status = 'close'
    db.session.commit()
    flash('Query closed / क्वेरी बंद हुई ✓', 'success')
    return redirect(url_for('queries'))

# ─── USER MANAGEMENT (admin only) ─────────────────────────────────────────────

@app.route('/users')
@login_required
@role_required('admin')
def users():
    all_users = User.query.all()
    return render_template('users.html', users=all_users)

@app.route('/users/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def add_user():
    if request.method == 'POST':
        f = request.form
        if User.query.filter_by(username=f['username']).first():
            flash('Username already exists / यूज़रनेम पहले से है', 'danger')
            return render_template('user_form.html', user=None)
        u = User(username=f['username'], name=f['name'], role=f['role'],
                 password=generate_password_hash(f['password']))
        db.session.add(u); db.session.commit()
        flash('User created / यूज़र बना ✓', 'success')
        return redirect(url_for('users'))
    return render_template('user_form.html', user=None)

@app.route('/users/edit/<int:uid>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_user(uid):
    u = User.query.get_or_404(uid)
    if request.method == 'POST':
        f = request.form
        u.name=f['name']; u.role=f['role']
        if f.get('password'):
            u.password = generate_password_hash(f['password'])
        db.session.commit()
        flash('User updated / अपडेट हो गया ✓', 'success')
        return redirect(url_for('users'))
    return render_template('user_form.html', user=u)

@app.route('/users/delete/<int:uid>', methods=['POST'])
@login_required
@role_required('admin')
def delete_user(uid):
    if uid == session['user_id']:
        flash('Cannot delete yourself / खुद को नहीं हटा सकते', 'danger')
        return redirect(url_for('users'))
    db.session.delete(User.query.get_or_404(uid))
    db.session.commit()
    flash('User deleted / हटाया गया', 'warning')
    return redirect(url_for('users'))

# ─── INIT DB ──────────────────────────────────────────────────────────────────

def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', name='Administrator',
                                role='admin', password=generate_password_hash('admin123')))
            db.session.commit()
            print("✓ Default admin created: admin / admin123")

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
