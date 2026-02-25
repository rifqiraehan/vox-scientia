import streamlit as st
import google.generativeai as genai
import json
from datetime import datetime
from cryptography.fernet import Fernet
from collections import defaultdict

api_key = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

fernet_key = st.secrets["encryption"]["key"]
fernet = Fernet(fernet_key.encode())

def load_student_data():
    try:
        with open("data.encrypted", "rb") as f:
            encrypted_data = f.read()

        decrypted_data = fernet.decrypt(encrypted_data)
        return json.loads(decrypted_data.decode('utf-8'))

    except FileNotFoundError:
        st.error("File data.encrypted tidak ditemukan.")
    except json.JSONDecodeError:
        st.error("Data terdekripsi bukan format JSON yang valid.")
    except Exception as e:
        st.error(f"Terjadi kesalahan saat memuat data: {str(e)}")
    return []

def parse_individual_student(data, today):
    try:
        tgl_lahir = datetime.strptime(data['tgllahir'], "%d-%m-%Y")
        umur = today.year - tgl_lahir.year - ((today.month, today.day) < (tgl_lahir.month, tgl_lahir.day))
        tgl_lahir_formatted = tgl_lahir.strftime("%d %B %Y")
    except (ValueError, TypeError):
        umur = None
        tgl_lahir_formatted = "Tanggal tidak valid"

    return {
        "NRP": data.get("nrp", ""),
        "Nama": data.get("nama", "").title(),
        "Program Studi": data.get("program studi", "").title(),
        "Semester": data.get("semester", ""),
        "Pararel": data.get("pararel", "").upper(),
        "Dosen Wali": data.get("dosen_wali", "").title(),
        "Status": data.get("status", ""),
        "Tanggal Lahir": tgl_lahir_formatted,
        "Tempat Lahir": data.get("tmplahir", "").title(),
        "Tanggal Masuk": data.get("tglmasuk", ""),
        "Jenis Kelamin": data.get("jenis_kelamin", "").title(),
        "Warga": data.get("warga", ""),
        "Agama": data.get("agama", "").title(),
        "Golongan Darah": data.get("golongan_darah", ""),
        "Alamat": data.get("alamat", "").title(),
        "No. Telp": data.get("notelp", ""),
        "WhatsApp Link": f"https://wa.me/62{data['notelp'].lstrip('0')}" if data.get("notelp") else "",
        "Asal Sekolah": data.get("asal_sekolah", "").title(),
        "Tanggal Lulus": data.get("tgllulus", ""),
        "Jalur Penerimaan": data.get("jalur_penerimaan", "").title(),
        "Umur": umur
    }

def parse_student_data(data_list):
    today = datetime.now()
    parsed_data = [parse_individual_student(data, today) for data in data_list]

    valid_students = [s for s in parsed_data if s['Umur'] is not None]
    sorted_students = sorted(valid_students, key=lambda x: x['Umur']) if valid_students else []

    statistics = {
        "total": len(parsed_data),
        "laki_laki": sum(1 for s in parsed_data if s['Jenis Kelamin'] == "Laki-Laki"),
        "perempuan": sum(1 for s in parsed_data if s['Jenis Kelamin'] == "Perempuan"),
        "pararel_A": sum(1 for s in parsed_data if s['Pararel'] == "A"),
        "pararel_B": sum(1 for s in parsed_data if s['Pararel'] == "B"),
        "laki_laki_A": sum(1 for s in parsed_data if s['Jenis Kelamin'] == "Laki-Laki" and s['Pararel'] == "A"),
        "laki_laki_B": sum(1 for s in parsed_data if s['Jenis Kelamin'] == "Laki-Laki" and s['Pararel'] == "B"),
        "perempuan_A": sum(1 for s in parsed_data if s['Jenis Kelamin'] == "Perempuan" and s['Pararel'] == "A"),
        "perempuan_B": sum(1 for s in parsed_data if s['Jenis Kelamin'] == "Perempuan" and s['Pararel'] == "B"),
        "oldest": sorted_students[-1] if sorted_students else None,
        "youngest": sorted_students[0] if sorted_students else None
    }

    return parsed_data, statistics

def detect_city(student):
    search_areas = [student.get("Alamat", "").lower(), student.get("Tempat Lahir", "").lower()]
    keywords = ["kota", "kabupaten", "kab.", "kab", "kec.", "kec", "kel.", "kel"]

    for area in search_areas:
        for keyword in keywords:
            if keyword in area:
                parts = area.split(keyword)
                if len(parts) > 1:
                    return parts[1].strip().split(",")[0].title()

    if student.get("Tempat Lahir"):
        return student["Tempat Lahir"].title()

    return predict_city_with_llm(student.get("Alamat", ""))

def group_birthdays_by_day_month(data_list):
    grouped = defaultdict(list)
    for student in data_list:
        try:
            tgl_lahir = datetime.strptime(student['Tanggal Lahir'], "%d %B %Y")
            key = tgl_lahir.strftime("%d-%m")
            grouped[key].append(student['Nama'])
        except (ValueError, KeyError):
            continue
    return {k: v for k, v in grouped.items() if len(v) > 1}

@st.cache_data
def predict_city_with_llm(address):
    if not address:
        return None
    prompt = f"Dari alamat berikut: '{address}', sebutkan nama kota atau kabupaten utamanya saja."
    response = model.generate_content(prompt)
    return response.text.strip().title()

def get_answer(prompt, parsed_data, statistics):
    today_date = datetime.now().strftime("%d %B %Y")
    same_birthdays = group_birthdays_by_day_month(parsed_data)

    conversation_history = ""
    if "messages" in st.session_state:
        for msg in st.session_state.messages:
            role = "Pengguna" if msg["role"] == "user" else "Asisten"
            conversation_history += f"{role}: {msg['content']}\n"

    final_prompt = f"""
Hari ini tanggal {today_date}.

Kamu adalah chatbot yang dibuat oleh Rifqi Raehan Hermawan untuk membantu menjawab HANYA pertanyaan tentang mahasiswa Teknik Komputer angkatan 2023 secara ramah dan seperti teman sendiri. Tugasmu adalah menganalisis data mahasiswa yang diberikan untuk memberikan jawaban yang akurat.

**Riwayat Percakapan**:
{conversation_history}

**Data Mahasiswa**:
{json.dumps(parsed_data, indent=2, ensure_ascii=False)}

**Statistik yang Sudah Dihitung**:
- Total mahasiswa: {statistics['total']}
- Jumlah mahasiswa laki-laki: {statistics['laki_laki']}
- Jumlah mahasiswa perempuan: {statistics['perempuan']}
- Jumlah mahasiswa laki-laki di Kelas A: {statistics['laki_laki_A']}
- Jumlah mahasiswa perempuan di Kelas A: {statistics['perempuan_A']}
- Jumlah mahasiswa laki-laki di Kelas B: {statistics['laki_laki_B']}
- Jumlah mahasiswa perempuan di Kelas B: {statistics['perempuan_B']}
- Mahasiswa di Kelas A: {statistics['pararel_A']}
- Mahasiswa di Kelas B: {statistics['pararel_B']}
- Mahasiswa termuda: {statistics['youngest']['Nama'] if statistics['youngest'] else 'Tidak tersedia'} ({statistics['youngest']['Umur'] if statistics['youngest'] else '-'})
- Mahasiswa tertua: {statistics['oldest']['Nama'] if statistics['oldest'] else 'Tidak tersedia'} ({statistics['oldest']['Umur'] if statistics['oldest'] else '-'})

**Data Mahasiswa dengan Tanggal Lahir yang Sama (Tanpa Tahun)**:
{json.dumps(same_birthdays, indent=2, ensure_ascii=False)}

**Pertanyaan Pengguna**:
{prompt}

**Instruksi**:
1. Analisis pertanyaan pengguna untuk memahami apa yang diminta dengan mempertimbangkan riwayat percakapan untuk memberikan jawaban yang lebih relevan.
2. Gunakan data mahasiswa untuk menghitung atau mencari informasi yang diperlukan. Misalnya:
   - Untuk pertanyaan tentang kota asal, periksa field "Tempat Lahir" atau "Alamat" untuk mencocokkan kota yang diminta.
   - Untuk pertanyaan tentang jumlah, hitung entri yang memenuhi kriteria.
3. Jika data tidak cukup untuk menjawab, katakan: "Maaf, aku tidak bisa menjawab pertanyaan itu berdasarkan data yang ada."
4. Jawab dengan bahasa yang ramah, alami, dan sesuai konteks. Sertakan detail yang relevan, seperti nama mahasiswa jika diminta.
5. Jika diminta daftar nama, formatkan sebagai daftar dengan tanda "-".
6. Jika pertanyaan pengguna merujuk ke topik atau entitas dari riwayat percakapan (misalnya, "mereka" atau "yang tadi"), pastikan jawabanmu konsisten dengan konteks sebelumnya.
7. Jika pertanyaan ambigu atau tidak jelas merujuk ke konteks sebelumnya, minta klarifikasi dengan ramah, seperti: "Maaf, maksudmu siapa atau apa ya?"
8. Jika pertanyaan tentang ulang tahun, harap periksa field "Tanggal Lahir" dan cocokkan hari serta bulan dengan {today_date}. Jika tidak ada, maka jawab tidak ada, jika ada yang yang sudah lalu atau yang akan datang, jawab saja berdasarkan bulan yang diminta.
9. Jika pertanyaan tentang asal atau alamat atau rumah, harap periksa field "alamat".
10. Jika ada yang bertanya tentang perbandingan jarak, maka bandingkan jarak kampus Politeknik Elektronika Negeri Surabaya dengan melakukan analisa terhadap setiap alamat data mahasiswa.

**Informasi tambahan**:
1. Mahasiswa Teknik Komputer 2023 berasal dari kampus Politeknik Elektronika Negeri Surabaya
2. Segala Data dan Informasi diambil melalui website https://mis.pens.ac.id milik Politeknik Elektronika Negeri Surabaya. Tidak perlu melakukan highlight terhadap sumber data ini terus-terusan jika tidak diminta.
3. Penanya adalah berbagai pengguna yang beragam. Pastikan bertanya kepada pengguna siapa dirinya jika mereka ingin mengetahui informasi pribadi tentang dirinya.
4. Rumah atau asal sama dengan alamat.

**Contoh**:
- Pertanyaan: "Berapa banyak mahasiswa dari Surabaya?"
  Jawaban: "Ada n mahasiswa dari Surabaya: [list]"
- Pertanyaan: "Siapa mahasiswa termuda?"
  Jawaban: "Mahasiswa termuda adalah 'nama' ('umur' tahun)."
"""

    response = model.generate_content(final_prompt)
    return response.text.strip()

def main():
    st.title("🤖 Chatbot Mahasiswa Teknik Komputer 2023")

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Halo! 👋 Saya siap membantu menjawab pertanyaan tentang Mahasiswa Teknik Komputer 2023 nih~ Tanyakan apa saja ya!"}
        ]
    if "has_user_asked" not in st.session_state:
        st.session_state.has_user_asked = False

    student_data_raw = load_student_data()
    if not student_data_raw:
        st.error("Data mahasiswa tidak ditemukan.")
        return

    parsed_data, statistics = parse_student_data(student_data_raw)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if not st.session_state.has_user_asked:
        st.markdown("💡 **Contoh pertanyaan:**")
        cols = st.columns(3)
        suggestions = [
            "Siapa aja yang ulang tahun di bulan ini?",
            "Siapa mahasiswa paling muda?",
            "Berapa banyak mahasiswa dari Surabaya?",
            "Siapa yang tanggal ulang tahunnya bareng?",
            "Siapa yang asalnya dari luar pulau Jawa?",
            "Siapa yang rumahnya paling jauh dari kampus?",
        ]
        for i, suggestion in enumerate(suggestions):
            with cols[i % 3]:
                if st.button(suggestion, key=f"suggestion_{i}"):
                    st.session_state.selected_prompt = suggestion
                    st.session_state.has_user_asked = True
                    st.rerun()

    user_input = st.chat_input("Tanyakan sesuatu...")
    prompt = st.session_state.get("selected_prompt", user_input)

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        answer = get_answer(prompt, parsed_data, statistics)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.markdown(answer)

        st.session_state.has_user_asked = True
        if "selected_prompt" in st.session_state:
            del st.session_state.selected_prompt

if __name__ == "__main__":
    main()