from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import pandas as pd
import io
import os
import shutil
import json

app = Flask(__name__)
app.secret_key = 'kgf-portal-secret-key-change-this'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)
DB_PATH = os.path.join(INSTANCE_DIR, 'kgf_portal.db')

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role     = db.Column(db.String(20), nullable=False)  # admin / manager / agent
    name     = db.Column(db.String(120))
    created  = db.Column(db.DateTime, default=datetime.utcnow)

class Activation(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    kgf_serial       = db.Column(db.Integer)
    kgf_id           = db.Column(db.String(20))
    member_name      = db.Column(db.String(120))
    amount           = db.Column(db.Float)
    contact          = db.Column(db.String(20))
    state            = db.Column(db.String(50))
    dist             = db.Column(db.String(50))
    status           = db.Column(db.String(30))
    payments         = db.Column(db.String(50))
    manager_name     = db.Column(db.String(100))
    date             = db.Column(db.Date)
    remark           = db.Column(db.String(200))
    utr_no           = db.Column(db.String(200))
    pay_confirm_by   = db.Column(db.String(100))
    payment_date     = db.Column(db.Date)
    created_by       = db.Column(db.String(80))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

class EditHistory(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    table_name   = db.Column(db.String(50))
    record_id    = db.Column(db.Integer)
    edited_by    = db.Column(db.String(80))
    edited_at    = db.Column(db.DateTime, default=datetime.utcnow)
    changes      = db.Column(db.Text)

class Cheque(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    member_name      = db.Column(db.String(120))
    contact          = db.Column(db.String(20))
    kgf_id           = db.Column(db.String(20))
    state            = db.Column(db.String(50))
    dist             = db.Column(db.String(50))
    cheque_status    = db.Column(db.String(30))
    cheque_no        = db.Column(db.String(50))
    cheque_date      = db.Column(db.Date)
    due_date         = db.Column(db.Date)
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
    pymt_date   = db.Column(db.Date)
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
    date              = db.Column(db.Date)
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

def parse_date(val):
    if not val or str(val).strip() == '':
        return None
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(str(val).strip(), fmt).date()
        except ValueError:
            continue
    return None

def record_edit(table_name, record_id, old_dict, new_dict):
    changes = {}
    for k in new_dict:
        old_val = str(old_dict.get(k, ''))
        new_val = str(new_dict.get(k, ''))
        if old_val != new_val:
            changes[k] = {'from': old_val, 'to': new_val}
    if changes:
        h = EditHistory(
            table_name=table_name,
            record_id=record_id,
            edited_by=session.get('username', '?'),
            changes=json.dumps(changes, ensure_ascii=False)
        )
        db.session.add(h)

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
            amount=f.get('amount') or 0,
            contact=f['contact'], state=f['state'], dist=f.get('dist'),
            status=f['status'], payments=f.get('payments'),
            manager_name=f.get('manager_name'), remark=f.get('remark'),
            utr_no=f.get('utr_no'), pay_confirm_by=f.get('pay_confirm_by'),
            payment_date=parse_date(f.get('payment_date')),
            date=parse_date(f.get('date')),
            created_by=session['username'])
        db.session.add(rec)
        db.session.commit()
        flash('Record added / रिकॉर्ड जोड़ा गया ✓', 'success')
        return redirect(url_for('activations'))
    return render_template('activation_form.html', rec=None)

@app.route('/activations/edit/<int:rid>', methods=['GET', 'POST'])
@login_required
def edit_activation(rid):
    if session.get('role') == 'agent':
        flash('Agents cannot edit records / एजेंट संपादन नहीं कर सकते', 'danger')
        return redirect(url_for('activations'))
    rec = Activation.query.get_or_404(rid)
    if request.method == 'POST':
        f = request.form
        old = {k: str(getattr(rec, k)) for k in ['kgf_id','member_name','amount','contact','state','dist','status','payments','manager_name','remark','utr_no','pay_confirm_by','payment_date','date']}
        rec.kgf_id=f['kgf_id']; rec.member_name=f['member_name']
        rec.amount=f.get('amount') or 0
        rec.contact=f['contact']; rec.state=f['state']; rec.dist=f.get('dist')
        rec.status=f['status']; rec.payments=f.get('payments')
        rec.manager_name=f.get('manager_name'); rec.remark=f.get('remark')
        rec.utr_no=f.get('utr_no'); rec.pay_confirm_by=f.get('pay_confirm_by')
        rec.payment_date=parse_date(f.get('payment_date'))
        rec.date=parse_date(f.get('date'))
        new = {k: str(getattr(rec, k)) for k in ['kgf_id','member_name','amount','contact','state','dist','status','payments','manager_name','remark','utr_no','pay_confirm_by','payment_date','date']}
        record_edit('activation', rid, old, new)
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
        lname = row.get('MANAGER NAME', row.get('LEADER NAME', ''))
        rec = Activation(
            kgf_serial=row.get('kgf'), kgf_id=str(row.get('ID','')),
            member_name=str(row.get('Name','')),
            amount=row.get('Amount') if pd.notna(row.get('Amount')) else 0,
            contact=str(row.get('Contact NO','')),
            state=str(row.get('STATE','')) if pd.notna(row.get('STATE')) else '',
            dist=str(row.get('Dist','')) if pd.notna(row.get('Dist')) else '',
            status=str(row.get('STATUS','')) if pd.notna(row.get('STATUS')) else '',
            payments=str(row.get('PAYMENTS','')) if pd.notna(row.get('PAYMENTS')) else '',
            manager_name=str(lname) if pd.notna(lname) else '',
            remark=str(row.get('REMARK','')) if pd.notna(row.get('REMARK')) else '',
            utr_no=str(row.get('UTR NO','')) if pd.notna(row.get('UTR NO')) else '',
            pay_confirm_by=str(row.get('PAY CONFIRM BY','')) if pd.notna(row.get('PAY CONFIRM BY')) else '',
            created_by='import')
        db.session.add(rec); count += 1
    db.session.commit()
    flash(f'{count} records imported / {count} रिकॉर्ड आयात हुए ✓', 'success')
    return redirect(url_for('activations'))

@app.route('/activations/export')
@login_required
def export_activations():
    records = Activation.query.all()
    data = [{'S.No': r.kgf_serial, 'KGF ID': r.kgf_id, 'Name': r.member_name,
              'Amount': r.amount, 'Contact': r.contact, 'State': r.state, 'Dist': r.dist,
              'Status': r.status, 'Payment Mode': r.payments, 'Manager': r.manager_name,
              'Date': r.date, 'Remark': r.remark, 'UTR No': r.utr_no,
              'Confirmed By': r.pay_confirm_by, 'Payment Date': r.payment_date} for r in records]
    df = pd.DataFrame(data); buf = io.BytesIO()
    df.to_excel(buf, index=False); buf.seek(0)
    return send_file(buf, download_name='activations_export.xlsx', as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/edit-history')
@login_required
@role_required('admin', 'manager')
def edit_history():
    table = request.args.get('table', '')
    query = EditHistory.query
    if table:
        query = query.filter_by(table_name=table)
    records = query.order_by(EditHistory.edited_at.desc()).limit(300).all()
    parsed = []
    for h in records:
        try:
            changes = json.loads(h.changes)
        except Exception:
            changes = {}
        parsed.append({'h': h, 'changes': changes})
    return render_template('edit_history.html', records=parsed, table=table)

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
                     cheque_date=parse_date(f.get('cheque_date')),
                     due_date=parse_date(f.get('due_date')),
                     package=f.get('package'), agreement_status=f.get('agreement_status'),
                     remarks=f.get('remarks'), created_by=session['username'])
        db.session.add(rec); db.session.commit()
        flash('Cheque record added / चेक रिकॉर्ड जोड़ा गया ✓', 'success')
        return redirect(url_for('cheques'))
    return render_template('cheque_form.html', rec=None)

@app.route('/cheques/edit/<int:rid>', methods=['GET', 'POST'])
@login_required
def edit_cheque(rid):
    if session.get('role') == 'agent':
        flash('Agents cannot edit / एजेंट संपादन नहीं कर सकते', 'danger')
        return redirect(url_for('cheques'))
    rec = Cheque.query.get_or_404(rid)
    if request.method == 'POST':
        f = request.form
        old = {k: str(getattr(rec, k)) for k in ['member_name','contact','kgf_id','cheque_status','cheque_no','cheque_date','due_date']}
        rec.member_name=f['member_name']; rec.contact=f['contact']
        rec.kgf_id=f['kgf_id']; rec.state=f['state']; rec.dist=f.get('dist')
        rec.cheque_status=f['cheque_status']; rec.cheque_no=f.get('cheque_no')
        rec.cheque_date=parse_date(f.get('cheque_date'))
        rec.due_date=parse_date(f.get('due_date'))
        rec.package=f.get('package'); rec.agreement_status=f.get('agreement_status')
        rec.remarks=f.get('remarks')
        new = {k: str(getattr(rec, k)) for k in ['member_name','contact','kgf_id','cheque_status','cheque_no','cheque_date','due_date']}
        record_edit('cheque', rid, old, new)
        db.session.commit()
        flash('Updated / अपडेट हो गया ✓', 'success')
        return redirect(url_for('cheques'))
    return render_template('cheque_form.html', rec=rec)

@app.route('/cheques/delete/<int:rid>', methods=['POST'])
@login_required
@role_required('admin')
def delete_cheque(rid):
    db.session.delete(Cheque.query.get_or_404(rid))
    db.session.commit()
    flash('Deleted / हटाया गया', 'warning')
    return redirect(url_for('cheques'))

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
@role_required('admin', 'manager')
def add_payout():
    if request.method == 'POST':
        f = request.form
        rec = Payout(benf_name=f['benf_name'], acc_no=f['acc_no'], ifsc=f['ifsc'],
                     amount=f.get('amount') or 0, userid=f['userid'],
                     pymt_date=parse_date(f.get('pymt_date')), bank=f.get('bank'),
                     status=f.get('status','Pending'), utr=f.get('utr'),
                     remarks=f.get('remarks'), created_by=session['username'])
        db.session.add(rec); db.session.commit()
        flash('Payout added / पेआउट जोड़ा गया ✓', 'success')
        return redirect(url_for('payouts'))
    return render_template('payout_form.html', rec=None)

@app.route('/payouts/edit/<int:rid>', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'manager')
def edit_payout(rid):
    rec = Payout.query.get_or_404(rid)
    if request.method == 'POST':
        f = request.form
        old = {k: str(getattr(rec, k)) for k in ['benf_name','amount','status','pymt_date']}
        rec.benf_name=f['benf_name']; rec.acc_no=f['acc_no']; rec.ifsc=f['ifsc']
        rec.amount=f.get('amount') or 0; rec.userid=f['userid']
        rec.pymt_date=parse_date(f.get('pymt_date')); rec.bank=f.get('bank')
        rec.status=f.get('status','Pending'); rec.utr=f.get('utr'); rec.remarks=f.get('remarks')
        new = {k: str(getattr(rec, k)) for k in ['benf_name','amount','status','pymt_date']}
        record_edit('payout', rid, old, new)
        db.session.commit()
        flash('Updated / अपडेट हो गया ✓', 'success')
        return redirect(url_for('payouts'))
    return render_template('payout_form.html', rec=rec)

@app.route('/payouts/delete/<int:rid>', methods=['POST'])
@login_required
@role_required('admin')
def delete_payout(rid):
    db.session.delete(Payout.query.get_or_404(rid))
    db.session.commit()
    flash('Deleted / हटाया गया', 'warning')
    return redirect(url_for('payouts'))

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
                    state=f.get('state'), dist=f.get('dist'),
                    date=parse_date(f.get('date')),
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
    if session.get('role') == 'agent':
        flash('Agents cannot edit / एजेंट संपादन नहीं कर सकते', 'danger')
        return redirect(url_for('queries'))
    rec = Query.query.get_or_404(rid)
    if request.method == 'POST':
        f = request.form
        old = {k: str(getattr(rec, k)) for k in ['member_name','status','remarks','date']}
        rec.member_name=f['member_name']; rec.contact=f['contact']
        rec.state=f.get('state'); rec.dist=f.get('dist')
        rec.date=parse_date(f.get('date'))
        rec.query_type=f.get('query_type'); rec.call_attender=f.get('call_attender')
        rec.department=f.get('department'); rec.remarks=f.get('remarks')
        rec.status=f.get('status','open'); rec.followup1=f.get('followup1')
        rec.followup2=f.get('followup2'); rec.followup3=f.get('followup3')
        new = {k: str(getattr(rec, k)) for k in ['member_name','status','remarks','date']}
        record_edit('query', rid, old, new)
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

@app.route('/queries/delete/<int:rid>', methods=['POST'])
@login_required
@role_required('admin')
def delete_query(rid):
    db.session.delete(Query.query.get_or_404(rid))
    db.session.commit()
    flash('Deleted / हटाया गया', 'warning')
    return redirect(url_for('queries'))

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

@app.route('/backup/download')
@login_required
@role_required('admin')
def backup_download():
    if not os.path.exists(DB_PATH):
        flash('Database file not found / डेटाबेस फाइल नहीं मिली', 'danger')
        return redirect(url_for('dashboard'))
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(DB_PATH, download_name=f'kgf_backup_{timestamp}.db',
                     as_attachment=True, mimetype='application/octet-stream')

@app.route('/backup/restore', methods=['POST'])
@login_required
@role_required('admin')
def backup_restore():
    f = request.files.get('backup_file')
    if not f or not f.filename.endswith('.db'):
        flash('Please upload a valid .db backup file / कृपया .db फाइल अपलोड करें', 'danger')
        return redirect(url_for('dashboard'))
    safety = DB_PATH + '.bak'
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, safety)
    try:
        f.save(DB_PATH)
        flash('Database restored! / डेटाबेस रिस्टोर हो गया ✓ — Please restart the app.', 'success')
    except Exception as e:
        if os.path.exists(safety):
            shutil.copy2(safety, DB_PATH)
        flash(f'Restore failed / रिस्टोर विफल: {e}', 'danger')
    return redirect(url_for('dashboard'))

def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', name='Administrator',
                                role='admin', password=generate_password_hash('admin123')))
            db.session.commit()
            print("✓ Default admin created: admin / admin123")
        print(f"✓ Database path: {DB_PATH}")

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
