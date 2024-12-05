from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
app = Flask(__name__)
CORS(app)
app.secret_key = 'supersecretkey'  # Güvenlik için

# Veritabanı ayarları
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///notlar.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Kullanıcı ve Not modelleri
class Kullanici(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    isim = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    sifre = db.Column(db.String(200), nullable=False)
    notlar = db.relationship('Not', backref='kullanici', lazy=True)

class Not(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    baslik = db.Column(db.String(200), nullable=False)
    icerik = db.Column(db.Text, nullable=False)
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    kullanici_id = db.Column(db.Integer, db.ForeignKey('kullanici.id'), nullable=False)

# Veritabanını oluşturma
with app.app_context():
    db.create_all()

@app.before_request
def kontrol_giris():
    if 'kullanici_id' not in session and request.endpoint not in ['giris', 'kayit', 'anasayfa']:
        return redirect(url_for('giris'))

@app.route('/kayit', methods=['GET', 'POST'])
def kayit():
    if request.method == 'POST':
        isim = request.form['isim']
        email = request.form['email']
        sifre = generate_password_hash(request.form['sifre'])

        # Veritabanında e-posta adresinin var olup olmadığını kontrol et
        mevcut_kullanici = Kullanici.query.filter_by(email=email).first()
        if mevcut_kullanici:
            flash('Bu e-posta adresi zaten kayıtlı. Lütfen başka bir e-posta adresi kullanın.', 'danger')
            return redirect(url_for('kayit'))

        # Yeni kullanıcıyı ekle
        yeni_kullanici = Kullanici(isim=isim, email=email, sifre=sifre)
        db.session.add(yeni_kullanici)
        try:
            db.session.commit()
            flash('Kayıt başarılı! Otomatik giriş yapılıyor...', 'success')
            session['kullanici_id'] = yeni_kullanici.id
            return redirect(url_for('loading'))
        except Exception as e:
            db.session.rollback()
            flash('Kayıt sırasında bir hata oluştu.', 'danger')
            return redirect(url_for('kayit'))

    return render_template('kayit.html')

@app.route('/loading')
def loading():
    return render_template('loading.html')

@app.route('/giris', methods=['GET', 'POST'])
def giris():
    if request.method == 'POST':
        email = request.form['email']
        sifre = request.form['sifre']
        kullanici = Kullanici.query.filter_by(email=email).first()

        if kullanici and check_password_hash(kullanici.sifre, sifre):
            session['kullanici_id'] = kullanici.id
            return redirect(url_for('profil'))
        else:
            flash('Hatalı e-posta veya şifre', 'danger')

    return render_template('giris.html')

@app.route('/profil')
def profil():
    kullanici = Kullanici.query.get(session['kullanici_id'])
    notlar = Not.query.filter_by(kullanici_id=kullanici.id).all()
    return render_template('profil.html', kullanici=kullanici, notlar=notlar)

@app.route('/not_olustur', methods=['POST'])
def not_olustur():
    baslik = request.form['baslik']
    icerik = request.form['icerik']
    kullanici_id = session['kullanici_id']

    yeni_not = Not(baslik=baslik, icerik=icerik, kullanici_id=kullanici_id)
    db.session.add(yeni_not)
    db.session.commit()

    flash('Yeni not başarıyla oluşturuldu!', 'success')
    return redirect(url_for('profil'))

@app.route('/api/not_sil/<int:not_id>', methods=['POST'])
def not_sil(not_id):
    not_obj = Not.query.get(not_id)
    if not_obj and not_obj.kullanici_id == session['kullanici_id']:
        db.session.delete(not_obj)
        db.session.commit()
        return {'message': 'Not başarıyla silindi.'}, 200
    else:
        return {'hata': 'Yetkiniz yok veya not bulunamadı.'}, 404

@app.route('/not_guncelle/<int:not_id>', methods=['GET', 'POST'])
def not_guncelle(not_id):
    not_obj = Not.query.get(not_id)
    
    # Kullanıcının doğru yetkilere sahip olup olmadığını kontrol et
    if not_obj and not_obj.kullanici_id == session.get('kullanici_id'):
        if request.method == 'POST':
            # Notu güncelleme işlemi
            not_obj.baslik = request.form['baslik']
            not_obj.icerik = request.form['icerik']
            db.session.commit()
            flash('Not başarıyla güncellendi!', 'success')
            return redirect(url_for('profil'))
        
        # GET isteğiyle notun mevcut verilerini yükleyerek düzenleme formunu göster
        return render_template('not_guncelle.html', not_obj=not_obj)
    else:
        flash('Yetkiniz yok veya not bulunamadı.', 'danger')
        return redirect(url_for('profil'))


@app.route('/cikis')
def cikis():
    session.pop('kullanici_id', None)
    flash('Çıkış başarılı.', 'info')
    return redirect(url_for('giris'))

@app.route('/api/not/<int:not_id>', methods=['GET'])
def not_detay(not_id):
    not_obj = Not.query.get(not_id)
    if not not_obj:
        return jsonify({"hata": "Not bulunamadı."}), 404
    
    return jsonify({
        "id": not_obj.id,
        "baslik": not_obj.baslik,
        "icerik": not_obj.icerik,
        "tarih": not_obj.tarih.strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/')
def anasayfa():
    return redirect(url_for('profil'))

if __name__ == '__main__':
    app.run(debug=True)
