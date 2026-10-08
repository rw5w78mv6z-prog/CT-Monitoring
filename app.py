from flask import Flask, render_template, request, jsonify
import os
import psycopg
from psycopg.rows import dict_row

app = Flask(__name__, template_folder=".")

# Online version: PostgreSQL database via DATABASE_URL environment variable.
# Render/Supabase can provide this URL. No local PC database is required.
DATABASE_URL = os.environ.get("DATABASE_URL")


def db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL belum diset. Atur DATABASE_URL pada hosting.")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db():
    with db() as c:
        with c.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS parts(
              id SERIAL PRIMARY KEY,
              part_no TEXT UNIQUE NOT NULL,
              part_name TEXT,
              model TEXT,
              ct_cost DOUBLE PRECISION,
              cavity TEXT
            );
            CREATE TABLE IF NOT EXISTS machines(
              id SERIAL PRIMARY KEY,
              name TEXT UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS shifts(
              id SERIAL PRIMARY KEY,
              name TEXT UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS records(
              id SERIAL PRIMARY KEY,
              date TEXT,
              machine TEXT,
              shift TEXT,
              part_no TEXT,
              part_name TEXT,
              model TEXT,
              ct_cost DOUBLE PRECISION,
              ct_actual DOUBLE PRECISION,
              ket TEXT
            );
            """)
            cur.execute("SELECT COUNT(*) AS n FROM parts")
            count = cur.fetchone()["n"]
            if count == 0:
                for p in SEED_PARTS:
                    cur.execute("""
                      INSERT INTO parts(part_no,part_name,model,ct_cost,cavity)
                      VALUES(%s,%s,%s,%s,%s) ON CONFLICT(part_no) DO NOTHING
                    """, (p["part_no"],p["part_name"],p["model"],p["ct_cost"],p["cavity"]))
                for m in SEED_MACHINES:
                    cur.execute("INSERT INTO machines(name) VALUES(%s) ON CONFLICT(name) DO NOTHING", (m,))
                for sh in SEED_SHIFTS:
                    cur.execute("INSERT INTO shifts(name) VALUES(%s) ON CONFLICT(name) DO NOTHING", (sh,))
                for r in SEED_RECORDS:
                    cur.execute("""
                      INSERT INTO records(date,machine,shift,part_no,part_name,model,ct_cost,ct_actual,ket)
                      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, r)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    try:
        with db() as c:
            with c.cursor() as cur:
                cur.execute("SELECT 1")
        return jsonify({"ok": True, "database": "connected"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/master")
def master():
    with db() as c:
        with c.cursor() as cur:
            out = {}
            for k in ["parts", "machines", "shifts"]:
                cur.execute(f"SELECT * FROM {k} ORDER BY id")
                out[k] = cur.fetchall()
    return jsonify(out)


@app.route("/api/part/<path:pn>")
def part(pn):
    with db() as c:
        with c.cursor() as cur:
            cur.execute("SELECT * FROM parts WHERE upper(part_no)=upper(%s)", (pn,))
            x = cur.fetchone()
    return jsonify(x if x else {})


@app.route("/api/records")
def get_records():
    with db() as c:
        with c.cursor() as cur:
            cur.execute("SELECT * FROM records ORDER BY date DESC,id DESC")
            rows = cur.fetchall()
    return jsonify(rows)


@app.post("/api/record")
def add_record():
    x = request.json or {}
    with db() as c:
        with c.cursor() as cur:
            cur.execute("SELECT * FROM parts WHERE upper(part_no)=upper(%s)", (x.get("part_no", ""),))
            p = cur.fetchone()
            if not p:
                return jsonify({"error":"Part No belum ada di Master Part"}), 400
            cur.execute("""
                INSERT INTO records(date,machine,shift,part_no,part_name,model,ct_cost,ct_actual,ket)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (x["date"],x["machine"],x["shift"],p["part_no"],p["part_name"],p["model"],p["ct_cost"],x["ct_actual"],x.get("ket", "")))
    return jsonify({"ok": True})


@app.post("/api/part")
def add_part():
    x = request.json or {}
    try:
        with db() as c:
            with c.cursor() as cur:
                cur.execute("""
                    INSERT INTO parts(part_no,part_name,model,ct_cost,cavity)
                    VALUES(%s,%s,%s,%s,%s)
                """, (x["part_no"],x.get("part_name",""),x.get("model",""),x.get("ct_cost",0),x.get("cavity","")))
    except psycopg.errors.UniqueViolation:
        return jsonify({"error":"Part No sudah ada"}), 400
    return jsonify({"ok": True})


@app.post("/api/machine")
def add_machine():
    x = request.json or {}
    try:
        with db() as c:
            with c.cursor() as cur:
                cur.execute("INSERT INTO machines(name) VALUES(%s)", (x["name"],))
    except psycopg.errors.UniqueViolation:
        return jsonify({"error":"Mesin sudah ada"}), 400
    return jsonify({"ok": True})


@app.post("/api/shift")
def add_shift():
    x = request.json or {}
    try:
        with db() as c:
            with c.cursor() as cur:
                cur.execute("INSERT INTO shifts(name) VALUES(%s)", (x["name"],))
    except psycopg.errors.UniqueViolation:
        return jsonify({"error":"Shift sudah ada"}), 400
    return jsonify({"ok": True})


@app.delete("/api/master/<kind>/<int:id>")
def delete_master(kind,id):
    if kind not in ("parts","machines","shifts"):
        return jsonify({"error":"invalid"}),400
    with db() as c:
        with c.cursor() as cur:
            cur.execute(f"DELETE FROM {kind} WHERE id=%s", (id,))
    return jsonify({"ok":True})


# Initialize database when the web service starts.
# Render will set DATABASE_URL before starting the service.
try:
    if DATABASE_URL:
        init_db()
except Exception as e:
    print("Database initialization warning:", e)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

SEED_PARTS=[{'part_no': 'AAN30005871', 'part_name': '2POLE BASE', 'model': '50/55NANO80 (25Y)', 'ct_cost': 120, 'cavity': ''}, {'part_no': 'AAN76009395S', 'part_name': '2POLE BASE', 'model': '43UP75', 'ct_cost': 75, 'cavity': ''}, {'part_no': 'MEA66414201MD', 'part_name': 'GUIDE PANEL', 'model': '55UA75', 'ct_cost': 78, 'cavity': ''}, {'part_no': 'AAN00858909', 'part_name': 'STAND BASE', 'model': '24/27LB70', 'ct_cost': 75, 'cavity': ''}, {'part_no': 'ACQ30836215', 'part_name': 'BACK COVER', 'model': '32LB65', 'ct_cost': 55, 'cavity': ''}, {'part_no': 'MEA66344201MD', 'part_name': 'GUIDE PANEL', 'model': '86NANO90', 'ct_cost': 75, 'cavity': ''}, {'part_no': 'MCK71206714MD', 'part_name': 'BACK COVER', 'model': 'OLED48C4PSA', 'ct_cost': 67.10521463166462, 'cavity': ''}, {'part_no': 'ACQ30816725', 'part_name': 'BACK COVER', 'model': '55UA75', 'ct_cost': 56, 'cavity': ''}, {'part_no': 'ACQ30851205', 'part_name': 'FRONT COVER', 'model': '65QNED81', 'ct_cost': 80, 'cavity': ''}, {'part_no': 'AAN30041953', 'part_name': '2POLE BASE', 'model': 'OLED42C2', 'ct_cost': 130, 'cavity': ''}, {'part_no': 'GBQ02-0611A-X1MD', 'part_name': 'CASE TOP', 'model': '75NU85', 'ct_cost': 65, 'cavity': ''}, {'part_no': 'AAN00855112', 'part_name': 'STAND BASE', 'model': 'OLED48/55/65B6', 'ct_cost': 164, 'cavity': ''}, {'part_no': '88513-Q6000', 'part_name': 'SUSPENSION SUB ASSY', 'model': 'Hyundai Sys', 'ct_cost': 65, 'cavity': ''}, {'part_no': 'AAN30078385', 'part_name': '2POLE BASE', 'model': '55UQ80', 'ct_cost': 98, 'cavity': ''}, {'part_no': 'MAZ67575033', 'part_name': 'STAND BODY TOP', 'model': 'OLEDC4', 'ct_cost': 110, 'cavity': ''}, {'part_no': 'MBN00647101MD', 'part_name': 'CASE TOP', 'model': '43UB85', 'ct_cost': 68, 'cavity': ''}, {'part_no': 'ACQ30804212', 'part_name': 'BACK COVER', 'model': '75UB85 CENTER', 'ct_cost': 65, 'cavity': ''}, {'part_no': 'MAM66002511MD', 'part_name': '2POLE BASE', 'model': '7075/86UQ90', 'ct_cost': 169, 'cavity': ''}, {'part_no': 'AAN00868207', 'part_name': 'STAND BASE', 'model': '65QNED81', 'ct_cost': 167, 'cavity': ''}, {'part_no': 'AAN76009396', 'part_name': '2POLE BASE', 'model': '43UP75', 'ct_cost': 75, 'cavity': ''}, {'part_no': 'MAM66002511', 'part_name': '2POLE BASE', 'model': '7075/86UQ90', 'ct_cost': 169, 'cavity': ''}, {'part_no': 'MCK30101901MD', 'part_name': 'BACK COVER', 'model': '27LB70', 'ct_cost': 55, 'cavity': ''}, {'part_no': 'LC65A221056AMD', 'part_name': 'CASE TOP', 'model': '65NU85', 'ct_cost': 65, 'cavity': ''}, {'part_no': 'MEA30022101MD', 'part_name': 'GUIDE PANEL', 'model': '55UH5Q', 'ct_cost': 52.87006802721089, 'cavity': ''}, {'part_no': 'MAZ30121101MD', 'part_name': 'STAND BODY TOP', 'model': '24/27LB70', 'ct_cost': 90, 'cavity': ''}, {'part_no': 'AAN30078231S', 'part_name': '2POLE BASE', 'model': '25Y 43NANO80', 'ct_cost': 86.5928110001394, 'cavity': ''}, {'part_no': 'MAZ67455313', 'part_name': 'STAND BODY TOP', 'model': '65,60,55NANO75UP80', 'ct_cost': 121, 'cavity': ''}, {'part_no': 'ACQ30678404', 'part_name': 'BOTTOM', 'model': '75/86UH5N', 'ct_cost': 74.93408055555557, 'cavity': ''}, {'part_no': 'MEA66365601MD', 'part_name': 'GUIDE PANEL', 'model': '86MLED95', 'ct_cost': 82, 'cavity': ''}, {'part_no': 'MBN00647901MD', 'part_name': 'CASE TOP', 'model': '75QNED80', 'ct_cost': 73, 'cavity': ''}, {'part_no': 'GAI02-1259A-X1MD', 'part_name': 'GUIDE PANEL', 'model': '75NU85', 'ct_cost': 75, 'cavity': ''}, {'part_no': 'ACQ30805415', 'part_name': 'BACK COVER', 'model': '85UB85 Center', 'ct_cost': 67, 'cavity': ''}, {'part_no': 'AAN00856002', 'part_name': 'STAND BASE', 'model': 'OLED77B6', 'ct_cost': 168, 'cavity': ''}, {'part_no': 'MEA30028701MD', 'part_name': 'GUIDE PANEL', 'model': '75UB85', 'ct_cost': 76, 'cavity': ''}, {'part_no': 'ACQ30606582', 'part_name': 'BACK COVER', 'model': '65UT80', 'ct_cost': 67, 'cavity': ''}, {'part_no': 'MBN00635501MD', 'part_name': 'CASE TOP', 'model': '55UH5Q', 'ct_cost': 66, 'cavity': ''}, {'part_no': 'ACQ30848618MD', 'part_name': 'BACK COVER', 'model': '43LB65 CENTER', 'ct_cost': 75, 'cavity': ''}, {'part_no': 'MEA30050601MD', 'part_name': '', 'model': '', 'ct_cost': 0, 'cavity': ''}, {'part_no': 'MBN00635601MD', 'part_name': 'CASE TOP', 'model': '65UH5Q', 'ct_cost': 66.286, 'cavity': ''}, {'part_no': 'MEA30022201MD', 'part_name': 'GUIDE PANEL', 'model': '65UH5Q', 'ct_cost': 61.5, 'cavity': ''}, {'part_no': 'AAN30078231', 'part_name': '2POLE BASE', 'model': '25Y 43NANO80', 'ct_cost': 86.5928110001394, 'cavity': ''}, {'part_no': 'MCK69958827MD', 'part_name': '2POLE BASE', 'model': '65UM73', 'ct_cost': 76, 'cavity': ''}, {'part_no': 'ACQ30805504MD', 'part_name': 'BACK COVER', 'model': '85UB85 Side Right', 'ct_cost': 68, 'cavity': ''}, {'part_no': 'MCK30092501MD', 'part_name': 'COVER, CABLE', 'model': '65QNED81', 'ct_cost': 75.999, 'cavity': ''}, {'part_no': 'ACQ30804221', 'part_name': 'BACK COVER', 'model': '75UB85 CENTER', 'ct_cost': 65, 'cavity': ''}, {'part_no': 'MCK71839305', 'part_name': 'Cable Cover, Stand', 'model': 'OLED55/65G4', 'ct_cost': 117.0539206349206, 'cavity': ''}, {'part_no': 'MEA30028801MD', 'part_name': 'GUIDE PANEL', 'model': '85UB85', 'ct_cost': 81.1, 'cavity': ''}, {'part_no': 'MCK30102301MD', 'part_name': 'COVER STAND', 'model': '24/27LB7000', 'ct_cost': 45, 'cavity': ''}, {'part_no': 'LC5010105601MD', 'part_name': 'GUIDE PANEL', 'model': '50UA75', 'ct_cost': 70, 'cavity': ''}, {'part_no': 'MAZ65337138MD', 'part_name': 'CABLE MANAGEMENT', 'model': 'OLED55/65C7/65E7', 'ct_cost': 45, 'cavity': ''}, {'part_no': 'ACQ30836209', 'part_name': 'BACK COVER', 'model': '32LB65', 'ct_cost': 55, 'cavity': ''}, {'part_no': 'MCK71839201MD', 'part_name': 'Front Cover, Stand', 'model': 'OLED55/65G4', 'ct_cost': 98, 'cavity': ''}, {'part_no': '53112-VT050', 'part_name': 'Grille Inside 560B', 'model': '560B', 'ct_cost': 60, 'cavity': ''}, {'part_no': 'MCK71570106MD', 'part_name': 'BOTTOM', 'model': '55G2/G3', 'ct_cost': 71.03476747474748, 'cavity': ''}, {'part_no': 'MCK30102002MD', 'part_name': 'BACK COVER', 'model': '24LB70', 'ct_cost': 55, 'cavity': ''}, {'part_no': 'ACQ30848609MD', 'part_name': 'BACK COVER', 'model': '43LB65 CENTER', 'ct_cost': 75, 'cavity': ''}, {'part_no': 'MEA66377304MD', 'part_name': 'GUIDE PANEL', 'model': '75QNED', 'ct_cost': 92, 'cavity': ''}, {'part_no': 'MAZ30120901MD', 'part_name': 'Bracket Side AV', 'model': '24/27LB7000', 'ct_cost': 40, 'cavity': ''}, {'part_no': 'LC55A221093AMD', 'part_name': 'CASE TOP', 'model': '55NU85', 'ct_cost': 60, 'cavity': ''}, {'part_no': 'MCK71575918MD', 'part_name': 'STAND BASE', 'model': 'OLED55/65C4', 'ct_cost': 126.4483531746032, 'cavity': ''}, {'part_no': 'AAN00855102', 'part_name': 'STAND BASE', 'model': 'OLED48/55/65B6', 'ct_cost': 164, 'cavity': ''}, {'part_no': 'MAZ67575044', 'part_name': 'STAND BODY TOP', 'model': 'OLEDC4', 'ct_cost': 110, 'cavity': ''}, {'part_no': 'ACQ30804305', 'part_name': 'BACK COVER', 'model': '75UB85 SIDE LEFT', 'ct_cost': 66.5, 'cavity': ''}, {'part_no': 'ACQ30805422', 'part_name': 'BACK COVER', 'model': '85UB85 Center', 'ct_cost': 67, 'cavity': ''}, {'part_no': 'ACQ30814840', 'part_name': 'BACK COVER', 'model': '50UA75', 'ct_cost': 56, 'cavity': ''}]
SEED_MACHINES=['A1', 'A2', 'A3', 'A6', 'A7', 'A8', 'A9', 'A11', 'A12', 'A13', 'A14', 'A15', 'A16', 'A18', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9', 'C10', 'C11', 'C12']
SEED_SHIFTS=['1', '2', '3']
SEED_RECORDS=[['2026-10-04', 'A3', '2', 'AAN30005871', '2POLE BASE', '50/55NANO80 (25Y)', 120, 135, 'GAS MARK'], ['2026-10-04', 'A3', '3', 'AAN30005871', '2POLE BASE', '50/55NANO80 (25Y)', 120, 135, 'GAS MARK'], ['2026-10-04', 'A14', '3', 'AAN76009395S', '2POLE BASE', '43UP75', 75, 88, 'SEMI AUTO'], ['2026-10-04', 'A14', '2', 'AAN76009395S', '2POLE BASE', '43UP75', 75, 88, 'SEMI AUTO'], ['2026-10-04', 'A14', '1', 'AAN76009395S', '2POLE BASE', '43UP75', 75, 85, 'SEMI AUTO[4 CAVITY]'], ['2026-10-04', 'C11', '1', 'MEA66414201MD', 'GUIDE PANEL', '55UA75', 78, 84.5, 'crack(need cleaning sirkulasi richi)'], ['2026-10-04', 'C11', '3', 'MEA66414201MD', 'GUIDE PANEL', '55UA75', 78, 84.2, 'CRACK AREA LOKING'], ['2026-10-04', 'A15', '3', 'AAN00858909', 'STAND BASE', '24/27LB70', 75, 75, 'OK'], ['2026-10-04', 'A15', '2', 'AAN00858909', 'STAND BASE', '24/27LB70', 75, 75, 'OK'], ['2026-10-04', 'A15', '1', 'AAN00858909', 'STAND BASE', '24/27LB70', 75, 75, 'OK'], ['2026-10-04', 'C7', '1', 'ACQ30836215', 'BACK COVER', '32LB65', 55, 54, 'OK'], ['2026-10-04', 'C8', '1', 'MEA66344201MD', 'GUIDE PANEL', '86NANO90', 75, 74, 'OK'], ['2026-10-04', 'C6', '3', 'MCK71206714MD', 'BACK COVER', 'OLED48C4PSA', 67.10521463166462, 64.8, 'OK'], ['2026-10-04', 'C6', '1', 'ACQ30816725', 'BACK COVER', '55UA75', 56, 52.6, 'OK'], ['2026-10-04', 'C6', '3', 'ACQ30816725', 'BACK COVER', '55UA75', 56, 52.6, 'OK'], ['2026-10-04', 'C8', '3', 'MEA66344201MD', 'GUIDE PANEL', '86NANO90', 75, 71, 'OK'], ['2026-10-04', 'A11', '3', 'ACQ30851205', 'FRONT COVER', '65QNED81', 80, 75, 'OK'], ['2026-10-04', 'A3', '1', 'AAN30041953', '2POLE BASE', 'OLED42C2', 130, 125, 'OK'], ['2026-10-04', 'A11', '1', 'ACQ30851205', 'FRONT COVER', '65QNED81', 80, 75, 'OK'], ['2026-10-04', 'A11', '2', 'ACQ30851205', 'FRONT COVER', '65QNED81', 80, 75, 'OK'], ['2026-10-04', 'C1', '3', 'GBQ02-0611A-X1MD', 'CASE TOP', '75NU85', 65, 57.2, 'OK'], ['2026-10-04', 'A8', '3', 'AAN00855112', 'STAND BASE', 'OLED48/55/65B6', 164, 154, 'OK'], ['2026-10-04', 'A8', '2', 'AAN00855112', 'STAND BASE', 'OLED48/55/65B6', 164, 154, 'OK'], ['2026-10-04', 'A18', '1', '88513-Q6000', 'SUSPENSION SUB ASSY', 'Hyundai Sys', 65, 54, 'OK'], ['2026-10-04', 'A8', '1', 'AAN00855112', 'STAND BASE', 'OLED48/55/65B6', 164, 153, 'OK'], ['2026-10-04', 'A9', '3', 'AAN30078385', '2POLE BASE', '55UQ80', 98, 85, 'OK'], ['2026-10-04', 'A2', '2', 'MAZ67575033', 'STAND BODY TOP', 'OLEDC4', 110, 97, 'OK'], ['2026-10-04', 'A9', '1', 'AAN30078385', '2POLE BASE', '55UQ80', 98, 85, 'OK'], ['2026-10-04', 'A2', '3', 'MAZ67575033', 'STAND BODY TOP', 'OLEDC4', 110, 97, 'OK'], ['2026-10-04', 'A9', '2', 'AAN30078385', '2POLE BASE', '55UQ80', 98, 85, 'OK'], ['2026-10-04', 'A2', '1', 'MAZ67575033', 'STAND BODY TOP', 'OLEDC4', 110, 96, 'OK'], ['2026-10-04', 'A7', '1', 'MBN00647101MD', 'CASE TOP', '43UB85', 68, 54, 'OK'], ['2026-10-04', 'A7', '2', 'MBN00647101MD', 'CASE TOP', '43UB85', 68, 54, 'OK'], ['2026-10-04', 'A1', '2', 'AAN00855112', 'STAND BASE', 'OLED48/55/65B6', 164, 147, 'OK'], ['2026-10-04', 'A1', '3', 'AAN00855112', 'STAND BASE', 'OLED48/55/65B6', 164, 147, 'OK'], ['2026-10-04', 'A1', '1', 'AAN00855112', 'STAND BASE', 'OLED48/55/65B6', 164, 147, 'OK'], ['2026-10-04', 'C4', '3', 'ACQ30804212', 'BACK COVER', '75UB85 CENTER', 65, 47, 'OK'], ['2026-10-04', 'C4', '1', 'ACQ30804212', 'BACK COVER', '75UB85 CENTER', 65, 46.5, 'OK'], ['2026-10-04', 'A12', '3', 'MAM66002511MD', '2POLE BASE', '7075/86UQ90', 169, 135, 'OK'], ['2026-10-04', 'C2', '1', 'AAN00868207', 'STAND BASE', '65QNED81', 167, 104, 'OK'], ['2026-10-04', 'C2', '3', 'AAN00868207', 'STAND BASE', '65QNED81', 167, 103, 'OK'], ['2026-10-04', 'C1', '1', 'GBQ02-0611A-X1MD', 'CASE TOP', '75NU85', 65, 0, 'OK'], ['2026-10-04', 'A12', '1', 'MAM66002511MD', '2POLE BASE', '7075/86UQ90', 169, 65.5, 'OK'], ['2026-10-04', 'A12', '2', 'MAM66002511MD', '2POLE BASE', '7075/86UQ90', 169, 0, 'OK'], ['2026-10-05', 'A14', '3', 'AAN76009396', '2POLE BASE', '43UP75', 75, 92, 'OPERATOR SEMI AUTO'], ['2026-10-05', 'A14', '2', 'AAN76009396', '2POLE BASE', '43UP75', 75, 92, 'OPERATOR SEMI AUTO'], ['2026-10-05', 'A14', '1', 'AAN76009396', '2POLE BASE', '43UP75', 75, 87, 'SEMI AUTO[4 CAVITY]'], ['2026-10-05', 'C11', '1', 'MEA66414201MD', 'GUIDE PANEL', '55UA75', 78, 84.2, 'CRACK AREA LOKING'], ['2026-10-05', 'A12', '1', 'MAM66002511', '2POLE BASE', '7075/86UQ90', 169, 175, 'SEMI AUTO[4 CAVITY]'], ['2026-10-05', 'A3', '1', 'AAN30005871', '2POLE BASE', '50/55NANO80 (25Y)', 120, 125, 'PART GASMARK'], ['2026-10-05', 'A11', '1', 'MCK30101901MD', 'BACK COVER', '27LB70', 55, 58, 'SHINMARK'], ['2026-10-05', 'C11', '3', 'MEA66414201MD', 'GUIDE PANEL', '55UA75', 78, 80.3, 'CRACK AREA LOKING'], ['2026-10-05', 'A11', '2', 'MCK30101901MD', 'BACK COVER', '27LB70', 55, 55, 'OK'], ['2026-10-05', 'A11', '3', 'MCK30101901MD', 'BACK COVER', '27LB70', 55, 55, 'OK'], ['2026-10-05', 'C10', '2', 'LC65A221056AMD', 'CASE TOP', '65NU85', 65, 64.75, 'OK'], ['2026-10-05', 'C10', '3', 'LC65A221056AMD', 'CASE TOP', '65NU85', 65, 64.75, 'OK'], ['2026-10-05', 'C7', '3', 'ACQ30836215', 'BACK COVER', '32LB65', 55, 54.5, 'OK'], ['2026-10-05', 'C7', '2', 'ACQ30836215', 'BACK COVER', '32LB65', 55, 54.5, 'OK'], ['2026-10-05', 'C10', '1', 'LC65A221056AMD', 'CASE TOP', '65NU85', 65, 64.5, 'OK'], ['2026-10-05', 'C2', '2', 'MEA30022101MD', 'GUIDE PANEL', '55UH5Q', 52.87006802721089, 50.3, 'OK'], ['2026-10-05', 'C2', '3', 'MEA30022101MD', 'GUIDE PANEL', '55UH5Q', 52.87006802721089, 50.3, 'OK'], ['2026-10-05', 'C8', '1', 'MEA66344201MD', 'GUIDE PANEL', '86NANO90', 75, 71, 'OK'], ['2026-10-05', 'C8', '2', 'MEA66344201MD', 'GUIDE PANEL', '86NANO90', 75, 70.5, 'OK'], ['2026-10-05', 'A15', '3', 'MAZ30121101MD', 'STAND BODY TOP', '24/27LB70', 90, 85, 'OK'], ['2026-10-05', 'A15', '2', 'MAZ30121101MD', 'STAND BODY TOP', '24/27LB70', 90, 85, 'OK'], ['2026-10-05', 'A15', '1', 'MAZ30121101MD', 'STAND BODY TOP', '24/27LB70', 90, 85, 'OK'], ['2026-10-05', 'A11', '1', 'ACQ30851205', 'FRONT COVER', '65QNED81', 80, 75, 'OK'], ['2026-10-05', 'A13', '3', 'AAN30078231S', '2POLE BASE', '25Y 43NANO80', 86.5928110001394, 81, 'OK'], ['2026-10-05', 'A13', '1', 'AAN30078231S', '2POLE BASE', '25Y 43NANO80', 86.5928110001394, 81, 'OK'], ['2026-10-05', 'A13', '2', 'AAN30078231S', '2POLE BASE', '25Y 43NANO80', 86.5928110001394, 81, 'OK'], ['2026-10-05', 'A3', '3', 'MAZ67455313', 'STAND BODY TOP', '65,60,55NANO75UP80', 121, 115, 'OK'], ['2026-10-05', 'A3', '2', 'MAZ67455313', 'STAND BODY TOP', '65,60,55NANO75UP80', 121, 115, 'OK'], ['2026-10-05', 'C6', '3', 'ACQ30678404', 'BOTTOM', '75/86UH5N', 74.93408055555557, 68.2, 'OK'], ['2026-10-05', 'C6', '2', 'ACQ30678404', 'BOTTOM', '75/86UH5N', 74.93408055555557, 68.2, 'OK'], ['2026-10-05', 'C6', '1', 'ACQ30678404', 'BOTTOM', '75/86UH5N', 74.93408055555557, 68.2, 'OK'], ['2026-10-05', 'C1', '1', 'GBQ02-0611A-X1MD', 'CASE TOP', '75NU85', 65, 57.2, 'OK'], ['2026-10-05', 'C1', '3', 'GBQ02-0611A-X1MD', 'CASE TOP', '75NU85', 65, 57, 'OK'], ['2026-10-05', 'C1', '2', 'GBQ02-0611A-X1MD', 'CASE TOP', '75NU85', 65, 57, 'OK'], ['2026-10-05', 'C8', '3', 'MEA66365601MD', 'GUIDE PANEL', '86MLED95', 82, 72.5, 'OK'], ['2026-10-05', 'A2', '3', 'MAZ67575033', 'STAND BODY TOP', 'OLEDC4', 110, 100, 'OK'], ['2026-10-05', 'A8', '2', 'AAN00855112', 'STAND BASE', 'OLED48/55/65B6', 164, 154, 'OK'], ['2026-10-05', 'A8', '3', 'AAN00855112', 'STAND BASE', 'OLED48/55/65B6', 164, 154, 'OK'], ['2026-10-05', 'A8', '1', 'AAN00855112', 'STAND BASE', 'OLED48/55/65B6', 164, 154, 'OK'], ['2026-10-05', 'A2', '1', 'MAZ67575033', 'STAND BODY TOP', 'OLEDC4', 110, 97, 'OK'], ['2026-10-05', 'A9', '1', 'AAN30078385', '2POLE BASE', '55UQ80', 98, 85, 'OK'], ['2026-10-05', 'A9', '3', 'AAN30078385', '2POLE BASE', '55UQ80', 98, 85, 'OK'], ['2026-10-05', 'A9', '2', 'AAN30078385', '2POLE BASE', '55UQ80', 98, 85, 'OK'], ['2026-10-05', 'C5', '3', 'MBN00647901MD', 'CASE TOP', '75QNED80', 73, 59.6, 'OK'], ['2026-10-05', 'C5', '2', 'MBN00647901MD', 'CASE TOP', '75QNED80', 73, 59.6, 'OK'], ['2026-10-05', 'C12', '2', 'GAI02-1259A-X1MD', 'GUIDE PANEL', '75NU85', 75, 60, 'OK'], ['2026-10-05', 'C12', '3', 'GAI02-1259A-X1MD', 'GUIDE PANEL', '75NU85', 75, 60, 'OK'], ['2026-10-05', 'C12', '1', 'GAI02-1259A-X1MD', 'GUIDE PANEL', '75NU85', 75, 60, 'OK'], ['2026-10-05', 'C3', '3', 'ACQ30805415', 'BACK COVER', '85UB85 Center', 67, 51.4, 'OK'], ['2026-10-05', 'C3', '2', 'ACQ30805415', 'BACK COVER', '85UB85 Center', 67, 51.4, 'OK'], ['2026-10-05', 'C3', '1', 'ACQ30805415', 'BACK COVER', '85UB85 Center', 67, 51.4, 'OK'], ['2026-10-05', 'A1', '3', 'AAN00856002', 'STAND BASE', 'OLED77B6', 168, 151, 'OK'], ['2026-10-05', 'C4', '1', 'ACQ30804212', 'BACK COVER', '75UB85 CENTER', 65, 47, 'OK'], ['2026-10-05', 'C4', '2', 'ACQ30804212', 'BACK COVER', '75UB85 CENTER', 65, 47, 'OK'], ['2026-10-05', 'C4', '3', 'ACQ30804212', 'BACK COVER', '75UB85 CENTER', 65, 47, 'OK'], ['2026-10-05', 'C5', '1', 'MEA30028701MD', 'GUIDE PANEL', '75UB85', 76, 47.2, 'OK'], ['2026-10-05', 'C2', '1', 'AAN00868207', 'STAND BASE', '65QNED81', 167, 103, 'OK'], ['2026-10-06', 'A14', '1', 'AAN76009396', '2POLE BASE', '43UP75', 75, 85, 'SEMI AUTO[4CAVITY]'], ['2026-10-06', 'C9', '2', 'ACQ30606582', 'BACK COVER', '65UT80', 67, 73.3, 'SHINKMARK AREA GATE'], ['2026-10-06', 'C11', '1', 'MEA66414201MD', 'GUIDE PANEL', '55UA75', 78, 84.2, 'CRACK AREA LOKING'], ['2026-10-06', 'C9', '3', 'ACQ30606582', 'BACK COVER', '65UT80', 67, 71.55, 'SINMAK AREA GATE'], ['2026-10-06', 'C10', '3', 'MBN00635501MD', 'CASE TOP', '55UH5Q', 66, 69, '× SILAHKAN TULIS ALASAN'], ['2026-10-06', 'C9', '1', 'ACQ30606582', 'BACK COVER', '65UT80', 67, 68, 'SINKMARK'], ['2026-10-06', 'A1', '3', 'ACQ30848618MD', 'BACK COVER', '43LB65 CENTER', 75, 75, 'OK'], ['2026-10-06', 'A1', '2', 'ACQ30848618MD', 'BACK COVER', '43LB65 CENTER', 75, 75, 'OK'], ['2026-10-06', 'C5', '1', 'MEA30050601MD', '', '', 0, 63.6, 'OK'], ['2026-10-06', 'C10', '2', 'MBN00635601MD', 'CASE TOP', '65UH5Q', 66.286, 65.7, 'OK'], ['2026-10-06', 'C10', '1', 'MBN00635601MD', 'CASE TOP', '65UH5Q', 66.286, 65.7, 'OK'], ['2026-10-06', 'C11', '2', 'MEA30022201MD', 'GUIDE PANEL', '65UH5Q', 61.5, 60.6, 'OK'], ['2026-10-06', 'C11', '3', 'MEA30022201MD', 'GUIDE PANEL', '65UH5Q', 61.5, 60.6, 'OK'], ['2026-10-06', 'C2', '2', 'MEA30022101MD', 'GUIDE PANEL', '55UH5Q', 52.87006802721089, 49.9, 'OK'], ['2026-10-06', 'C2', '1', 'MEA30022101MD', 'GUIDE PANEL', '55UH5Q', 52.87006802721089, 49.9, 'OK'], ['2026-10-06', 'A2', '3', 'MAZ67575033', 'STAND BODY TOP', 'OLEDC4', 110, 107, 'OK'], ['2026-10-06', 'C8', '1', 'MEA66344201MD', 'GUIDE PANEL', '86NANO90', 75, 71.8, 'OK'], ['2026-10-06', 'A15', '1', 'MAZ30121101MD', 'STAND BODY TOP', '24/27LB70', 90, 85, 'OK'], ['2026-10-06', 'A13', '3', 'AAN30078231', '2POLE BASE', '25Y 43NANO80', 86.5928110001394, 81, 'OK'], ['2026-10-06', 'A13', '1', 'AAN30078231', '2POLE BASE', '25Y 43NANO80', 86.5928110001394, 81, 'OK'], ['2026-10-06', 'A13', '2', 'AAN30078231', '2POLE BASE', '25Y 43NANO80', 86.5928110001394, 81, 'OK'], ['2026-10-06', 'C10', '3', 'MBN00635601MD', 'CASE TOP', '65UH5Q', 66.286, 60, 'OK'], ['2026-10-06', 'C6', '1', 'ACQ30678404', 'BOTTOM', '75/86UH5N', 74.93408055555557, 68, 'OK'], ['2026-10-06', 'C1', '2', 'GBQ02-0611A-X1MD', 'CASE TOP', '75NU85', 65, 57.2, 'OK'], ['2026-10-06', 'C1', '1', 'GBQ02-0611A-X1MD', 'CASE TOP', '75NU85', 65, 57.2, 'OK'], ['2026-10-06', 'C1', '3', 'GBQ02-0611A-X1MD', 'CASE TOP', '75NU85', 65, 57.2, 'OK'], ['2026-10-06', 'A8', '1', 'AAN00855112', 'STAND BASE', 'OLED48/55/65B6', 164, 154, 'OK'], ['2026-10-06', 'A3', '3', 'MCK69958827MD', '2POLE BASE', '65UM73', 76, 63, 'OK'], ['2026-10-06', 'A2', '1', 'MAZ67575033', 'STAND BODY TOP', 'OLEDC4', 110, 97, 'OK'], ['2026-10-06', 'A3', '2', 'MCK69958827MD', '2POLE BASE', '65UM73', 76, 63, 'OK'], ['2026-10-06', 'A9', '2', 'AAN30078385', '2POLE BASE', '55UQ80', 98, 85, 'OK'], ['2026-10-06', 'A2', '2', 'MAZ67575033', 'STAND BODY TOP', 'OLEDC4', 110, 97, 'OK'], ['2026-10-06', 'A9', '3', 'AAN30078385', '2POLE BASE', '55UQ80', 98, 85, 'OK'], ['2026-10-06', 'A3', '1', 'MCK69958827MD', '2POLE BASE', '65UM73', 76, 63, 'OK'], ['2026-10-06', 'A9', '1', 'AAN30078385', '2POLE BASE', '55UQ80', 98, 85, 'OK'], ['2026-10-06', 'C12', '2', 'GAI02-1259A-X1MD', 'GUIDE PANEL', '75NU85', 75, 60, 'OK'], ['2026-10-06', 'C12', '1', 'GAI02-1259A-X1MD', 'GUIDE PANEL', '75NU85', 75, 60, 'OK'], ['2026-10-06', 'C12', '3', 'GAI02-1259A-X1MD', 'GUIDE PANEL', '75NU85', 75, 60, 'OK'], ['2026-10-06', 'A1', '1', 'AAN00856002', 'STAND BASE', 'OLED77B6', 168, 151, 'OK'], ['2026-10-06', 'C4', '1', 'ACQ30804212', 'BACK COVER', '75UB85 CENTER', 65, 47.1, 'OK'], ['2026-10-06', 'C4', '2', 'ACQ30804212', 'BACK COVER', '75UB85 CENTER', 65, 47.1, 'OK'], ['2026-10-06', 'C3', '1', 'ACQ30805415', 'BACK COVER', '85UB85 Center', 67, 48.8, 'OK'], ['2026-10-06', 'C3', '2', 'ACQ30805415', 'BACK COVER', '85UB85 Center', 67, 48.8, 'OK'], ['2026-10-06', 'C3', '3', 'ACQ30805504MD', 'BACK COVER', '85UB85 Side Right', 68, 48.8, 'OK'], ['2026-10-06', 'A11', '2', 'MCK30092501MD', 'COVER, CABLE', '65QNED81', 75.999, 56, 'OK'], ['2026-10-06', 'A11', '3', 'MCK30092501MD', 'COVER, CABLE', '65QNED81', 75.999, 56, 'OK'], ['2026-10-06', 'C4', '3', 'ACQ30804221', 'BACK COVER', '75UB85 CENTER', 65, 45, 'OK'], ['2026-10-06', 'A11', '1', 'MCK30092501MD', 'COVER, CABLE', '65QNED81', 75.999, 55, 'OK'], ['2026-10-06', 'A15', '2', 'MCK71839305', 'Cable Cover, Stand', 'OLED55/65G4', 117.0539206349206, 84, 'OK'], ['2026-10-06', 'A15', '3', 'MCK71839305', 'Cable Cover, Stand', 'OLED55/65G4', 117.0539206349206, 84, 'OK'], ['2026-10-06', 'C5', '2', 'MEA30028801MD', 'GUIDE PANEL', '85UB85', 81.1, 42, 'OK'], ['2026-10-06', 'C5', '3', 'MEA30028801MD', 'GUIDE PANEL', '85UB85', 81.1, 42, 'OK'], ['2026-10-06', 'A14', '3', 'MCK30102301MD', 'COVER STAND', '24/27LB7000', 45, 0, 'OK'], ['2026-10-06', 'C2', '3', 'AAN00868207', 'STAND BASE', '65QNED81', 167, 114, 'OK'], ['2026-10-07', 'C11', '3', 'LC5010105601MD', 'GUIDE PANEL', '50UA75', 70, 77.7, 'CRACKING AREA LOKING'], ['2026-10-07', 'A14', '1', 'MCK30102301MD', 'COVER STAND', '24/27LB7000', 45, 50, 'SEMI AUTO'], ['2026-10-07', 'A16', '1', 'MAZ65337138MD', 'CABLE MANAGEMENT', 'OLED55/65C7/65E7', 45, 50, 'SEMI AUTO'], ['2026-10-07', 'A16', '2', 'MAZ65337138MD', 'CABLE MANAGEMENT', 'OLED55/65C7/65E7', 45, 50, 'SEMI AUTO'], ['2026-10-07', 'A15', '1', 'MCK71839305', 'Cable Cover, Stand', 'OLED55/65G4', 117.0539206349206, 120, 'SEMI AUTO'], ['2026-10-07', 'A15', '2', 'MCK71839305', 'Cable Cover, Stand', 'OLED55/65G4', 117.0539206349206, 120, 'SEMI AUTO'], ['2026-10-07', 'A15', '3', 'MCK71839305', 'Cable Cover, Stand', 'OLED55/65G4', 117.0539206349206, 120, 'SEMI AUTO'], ['2026-10-07', 'C7', '1', 'ACQ30836209', 'BACK COVER', '32LB65', 55, 55.3, 'SINKMARK'], ['2026-10-07', 'A14', '3', 'MCK71839201MD', 'Front Cover, Stand', 'OLED55/65G4', 98, 98, 'OK'], ['2026-10-07', 'A1', '2', '53112-VT050', 'Grille Inside 560B', '560B', 60, 60, 'OK'], ['2026-10-07', 'A14', '2', 'MCK71839201MD', 'Front Cover, Stand', 'OLED55/65G4', 98, 98, 'OK'], ['2026-10-07', 'A1', '3', '53112-VT050', 'Grille Inside 560B', '560B', 60, 60, 'OK'], ['2026-10-07', 'C7', '2', 'ACQ30836209', 'BACK COVER', '32LB65', 55, 55, 'OK'], ['2026-10-07', 'C7', '3', 'ACQ30836209', 'BACK COVER', '32LB65', 55, 55, 'OK'], ['2026-10-07', 'C2', '1', 'MCK71570106MD', 'BOTTOM', '55G2/G3', 71.03476747474748, 70.28, 'OK'], ['2026-10-07', 'C10', '1', 'MBN00635501MD', 'CASE TOP', '55UH5Q', 66, 65, 'OK'], ['2026-10-07', 'C10', '2', 'MBN00635501MD', 'CASE TOP', '55UH5Q', 66, 65, 'OK'], ['2026-10-07', 'A11', '3', 'MCK30102002MD', 'BACK COVER', '24LB70', 55, 54, 'OK'], ['2026-10-07', 'C10', '3', 'MBN00635501MD', 'CASE TOP', '55UH5Q', 66, 65, 'OK'], ['2026-10-07', 'A11', '2', 'MCK30102002MD', 'BACK COVER', '24LB70', 55, 54, 'OK'], ['2026-10-07', 'A1', '1', 'ACQ30848609MD', 'BACK COVER', '43LB65 CENTER', 75, 74, 'OK'], ['2026-10-07', 'C11', '1', 'MEA30022201MD', 'GUIDE PANEL', '65UH5Q', 61.5, 60, 'OK'], ['2026-10-07', 'C11', '2', 'MEA30022201MD', 'GUIDE PANEL', '65UH5Q', 61.5, 60, 'OK'], ['2026-10-07', 'C8', '3', 'MEA66377304MD', 'GUIDE PANEL', '75QNED', 92, 88.1, 'OK'], ['2026-10-07', 'A16', '3', 'MAZ30120901MD', 'Bracket Side AV', '24/27LB7000', 40, 34, 'OK'], ['2026-10-07', 'A7', '3', 'LC55A221093AMD', 'CASE TOP', '55NU85', 60, 53, 'OK'], ['2026-10-07', 'A7', '2', 'LC55A221093AMD', 'CASE TOP', '55NU85', 60, 53, 'OK'], ['2026-10-07', 'A7', '1', 'LC55A221093AMD', 'CASE TOP', '55NU85', 60, 53, 'OK'], ['2026-10-07', 'A3', '1', 'MCK71575918MD', 'STAND BASE', 'OLED55/65C4', 126.4483531746032, 118, 'OK'], ['2026-10-07', 'A3', '2', 'MCK71575918MD', 'STAND BASE', 'OLED55/65C4', 126.4483531746032, 118, 'OK'], ['2026-10-07', 'A3', '3', 'MCK71575918MD', 'STAND BASE', 'OLED55/65C4', 126.4483531746032, 118, 'OK'], ['2026-10-07', 'A8', '1', 'AAN00855102', 'STAND BASE', 'OLED48/55/65B6', 164, 154, 'OK'], ['2026-10-07', 'A2', '1', 'MAZ67575044', 'STAND BODY TOP', 'OLEDC4', 110, 100, 'OK'], ['2026-10-07', 'A2', '3', 'MAZ67575044', 'STAND BODY TOP', 'OLEDC4', 110, 100, 'OK'], ['2026-10-07', 'A2', '2', 'MAZ67575044', 'STAND BODY TOP', 'OLEDC4', 110, 100, 'OK'], ['2026-10-07', 'C2', '3', 'ACQ30805504MD', 'BACK COVER', '85UB85 Side Right', 68, 57.9, 'OK'], ['2026-10-07', 'C8', '1', 'MEA66365601MD', 'GUIDE PANEL', '86MLED95', 82, 71.8, 'OK'], ['2026-10-07', 'C8', '2', 'MEA66365601MD', 'GUIDE PANEL', '86MLED95', 82, 71.8, 'OK'], ['2026-10-07', 'C1', '2', 'GBQ02-0611A-X1MD', 'CASE TOP', '75NU85', 65, 54.2, 'OK'], ['2026-10-07', 'C1', '3', 'GBQ02-0611A-X1MD', 'CASE TOP', '75NU85', 65, 54.2, 'OK'], ['2026-10-07', 'C1', '1', 'GBQ02-0611A-X1MD', 'CASE TOP', '75NU85', 65, 54.2, 'OK'], ['2026-10-07', 'A13', '1', 'AAN30078231', '2POLE BASE', '25Y 43NANO80', 86.5928110001394, 75, 'OK'], ['2026-10-07', 'A13', '3', 'AAN30078231', '2POLE BASE', '25Y 43NANO80', 86.5928110001394, 75, 'OK'], ['2026-10-07', 'A13', '2', 'AAN30078231', '2POLE BASE', '25Y 43NANO80', 86.5928110001394, 75, 'OK'], ['2026-10-07', 'A9', '2', 'AAN30078385', '2POLE BASE', '55UQ80', 98, 85, 'OK'], ['2026-10-07', 'A9', '3', 'AAN30078385', '2POLE BASE', '55UQ80', 98, 85, 'OK'], ['2026-10-07', 'A9', '1', 'AAN30078385', '2POLE BASE', '55UQ80', 98, 85, 'OK'], ['2026-10-07', 'A6', '3', 'ACQ30804305', 'BACK COVER', '75UB85 SIDE LEFT', 66.5, 53, 'OK'], ['2026-10-07', 'A6', '1', 'ACQ30804305', 'BACK COVER', '75UB85 SIDE LEFT', 66.5, 53, 'OK'], ['2026-10-07', 'A6', '2', 'ACQ30804305', 'BACK COVER', '75UB85 SIDE LEFT', 66.5, 53, 'OK'], ['2026-10-07', 'C2', '2', 'ACQ30805504MD', 'BACK COVER', '85UB85 Side Right', 68, 53.4, 'OK'], ['2026-10-07', 'C3', '3', 'ACQ30805422', 'BACK COVER', '85UB85 Center', 67, 52.4, 'OK'], ['2026-10-07', 'C3', '2', 'ACQ30805422', 'BACK COVER', '85UB85 Center', 67, 52.4, 'OK'], ['2026-10-07', 'C12', '3', 'GAI02-1259A-X1MD', 'GUIDE PANEL', '75NU85', 75, 60, 'OK'], ['2026-10-07', 'C12', '2', 'GAI02-1259A-X1MD', 'GUIDE PANEL', '75NU85', 75, 60, 'OK'], ['2026-10-07', 'C12', '1', 'GAI02-1259A-X1MD', 'GUIDE PANEL', '75NU85', 75, 60, 'OK'], ['2026-10-07', 'A11', '1', 'MCK30092501MD', 'COVER, CABLE', '65QNED81', 75.999, 57, 'OK'], ['2026-10-07', 'C3', '1', 'ACQ30805504MD', 'BACK COVER', '85UB85 Side Right', 68, 48.8, 'OK'], ['2026-10-07', 'C4', '1', 'ACQ30804221', 'BACK COVER', '75UB85 CENTER', 65, 45, 'OK'], ['2026-10-07', 'C4', '2', 'ACQ30804221', 'BACK COVER', '75UB85 CENTER', 65, 45, 'OK'], ['2026-10-07', 'C4', '3', 'ACQ30804221', 'BACK COVER', '75UB85 CENTER', 65, 44.9, 'OK'], ['2026-10-07', 'C5', '1', 'MEA30028801MD', 'GUIDE PANEL', '85UB85', 81.1, 42.7, 'OK'], ['2026-10-07', 'C5', '2', 'MEA30028801MD', 'GUIDE PANEL', '85UB85', 81.1, 42.7, 'OK'], ['2026-10-07', 'C5', '3', 'MEA30028801MD', 'GUIDE PANEL', '85UB85', 81.1, 42.7, 'OK'], ['2026-10-08', 'C11', '1', 'LC5010105601MD', 'GUIDE PANEL', '50UA75', 70, 77.7, 'CRACKING AREA LOKING'], ['2026-10-08', 'C7', '1', 'ACQ30836209', 'BACK COVER', '32LB65', 55, 55, 'OK'], ['2026-10-08', 'C10', '1', 'MBN00635501MD', 'CASE TOP', '55UH5Q', 66, 65, 'OK'], ['2026-10-08', 'C8', '1', 'MEA66377304MD', 'GUIDE PANEL', '75QNED', 92, 88.1, 'OK'], ['2026-10-08', 'C2', '1', 'ACQ30805504MD', 'BACK COVER', '85UB85 Side Right', 68, 57.9, 'OK'], ['2026-10-08', 'C1', '1', 'GBQ02-0611A-X1MD', 'CASE TOP', '75NU85', 65, 54.2, 'OK'], ['2026-10-08', 'C3', '1', 'ACQ30805422', 'BACK COVER', '85UB85 Center', 67, 52.4, 'OK'], ['2026-10-08', 'C4', '1', 'ACQ30804221', 'BACK COVER', '75UB85 CENTER', 65, 44.9, 'OK'], ['2026-10-08', 'C5', '1', 'MEA30028801MD', 'GUIDE PANEL', '85UB85', 81.1, 42.7, 'OK'], ['2026-10-08', 'C6', '1', 'ACQ30814840', 'BACK COVER', '50UA75', 56, 0, 'OK']]

if __name__=="__main__":
    init_db()
    app.run(host="0.0.0.0",port=5000,debug=False)
