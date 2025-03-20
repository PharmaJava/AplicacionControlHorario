import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import datetime
import pandas as pd
import os
import shutil
from cryptography.fernet import Fernet

class TimeTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Control Horario - España")
        self.root.geometry("800x600")
        self.root.configure(bg="#B3CDE0")

        self.admin_password = "RepublicaArgentina"
        self.key = Fernet.generate_key()
        self.cipher = Fernet(self.key)

        app_data_dir = os.path.join(os.getenv('APPDATA'), 'ControlHorario')
        os.makedirs(app_data_dir, exist_ok=True)
        db_path = os.path.join(app_data_dir, 'time_tracker.db')
        self.conn = sqlite3.connect(db_path)
        self.create_tables()

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TButton", padding=10, relief="flat", background="#6497B1", 
                            foreground="white", font=("Arial", 10, "bold"), borderwidth=0)
        self.style.map("TButton", background=[('active', '#03396C')], foreground=[('active', 'white')])
        self.style.configure("TLabel", background="#B3CDE0", foreground="#03396C", font=("Arial", 11))
        self.style.configure("TEntry", fieldbackground="white", foreground="#03396C", font=("Arial", 10))
        self.style.configure("Custom.TFrame", background="#B3CDE0")

        self.main_frame = ttk.Frame(root, padding="30", style="Custom.TFrame")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.create_widgets()
        ttk.Label(self.root, text="PharmaJava © 2025", 
                 font=("Arial", 8, "italic"), foreground="#03396C").place(relx=0.90, rely=0.95)

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                         (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                          name TEXT, 
                          encrypted_name BLOB)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS records 
                         (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                          user_id INTEGER, 
                          entry_time TEXT, 
                          exit_time TEXT,
                          FOREIGN KEY(user_id) REFERENCES users(id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS incidents 
                         (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                          user_id INTEGER, 
                          incident_time TEXT,
                          FOREIGN KEY(user_id) REFERENCES users(id))''')
        self.conn.commit()

    def create_widgets(self):
        ttk.Label(self.main_frame, text="Nombre:").grid(row=0, column=0, pady=15, padx=10, sticky="e")
        self.name_entry = ttk.Entry(self.main_frame, width=35)
        self.name_entry.grid(row=0, column=1, pady=15, padx=10)
        ttk.Button(self.main_frame, text="Crear Usuario", 
                  command=self.create_user).grid(row=0, column=2, padx=15, pady=15)
        ttk.Button(self.main_frame, text="Modificar Usuario", 
                  command=self.modify_user).grid(row=0, column=3, padx=15, pady=15)

        ttk.Label(self.main_frame, text="ID Usuario:").grid(row=1, column=0, pady=15, padx=10, sticky="e")
        self.id_entry = ttk.Entry(self.main_frame, width=35)
        self.id_entry.grid(row=1, column=1, pady=15, padx=10)

        ttk.Button(self.main_frame, text="Registrar Entrada", 
                  command=self.register_entry).grid(row=2, column=0, pady=15, padx=10)
        ttk.Button(self.main_frame, text="Registrar Salida", 
                  command=self.register_exit).grid(row=2, column=1, pady=15, padx=10)
        ttk.Button(self.main_frame, text="Registrar Incidencia", 
                  command=self.register_incident).grid(row=2, column=2, pady=15, padx=10)

        ttk.Button(self.main_frame, text="Exportar a Excel", 
                  command=self.export_to_excel).grid(row=3, column=0, pady=15, padx=10)
        ttk.Button(self.main_frame, text="Hacer Backup", 
                  command=self.backup_db).grid(row=3, column=1, pady=15, padx=10)

        self.records_text = tk.Text(self.main_frame, height=20, width=80, 
                                   bg="white", fg="#03396C", font=("Arial", 10), 
                                   borderwidth=2, relief="groove")
        self.records_text.grid(row=4, column=0, columnspan=4, pady=20)
        self.update_records_display()

    def check_admin_password(self):
        password = simpledialog.askstring("Clave de Administrador", "Ingrese la clave:", show="*")
        return password == self.admin_password

    def create_user(self):
        if not self.check_admin_password():
            messagebox.showerror("Error", "Clave de administrador incorrecta")
            return
        
        name = self.name_entry.get()
        if name:
            cursor = self.conn.cursor()
            encrypted_name = self.cipher.encrypt(name.encode())
            cursor.execute("INSERT INTO users (name, encrypted_name) VALUES (?, ?)", 
                          (name, encrypted_name))
            self.conn.commit()
            user_id = cursor.lastrowid
            messagebox.showinfo("Éxito", f"Usuario creado: {name} - ID: {user_id}")
            self.name_entry.delete(0, tk.END)
            self.update_records_display()
        else:
            messagebox.showerror("Error", "Por favor ingrese un nombre")

    def modify_user(self):
        if not self.check_admin_password():
            messagebox.showerror("Error", "Clave de administrador incorrecta")
            return
        
        user_id = self.id_entry.get()
        if not user_id:
            messagebox.showerror("Error", "Por favor ingrese un ID de usuario")
            return
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        
        if not result:
            messagebox.showerror("Error", f"No se encontró un usuario con ID {user_id}")
            return
        
        current_name = result[0]
        new_name = simpledialog.askstring("Modificar Usuario", 
                                         f"Nombre actual: {current_name}\nNuevo nombre:", 
                                         initialvalue=current_name)
        
        if new_name:
            encrypted_name = self.cipher.encrypt(new_name.encode())
            cursor.execute("UPDATE users SET name = ?, encrypted_name = ? WHERE id = ?", 
                          (new_name, encrypted_name, user_id))
            self.conn.commit()
            messagebox.showinfo("Éxito", f"Usuario ID {user_id} actualizado a: {new_name}")
            self.id_entry.delete(0, tk.END)
            self.update_records_display()
        else:
            messagebox.showinfo("Cancelado", "No se realizaron cambios")

    def register_entry(self):
        user_id = self.id_entry.get()
        if user_id:
            cursor = self.conn.cursor()
            current_time = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            cursor.execute("SELECT id FROM records WHERE user_id = ? AND exit_time IS NULL", 
                          (user_id,))
            if cursor.fetchone():
                messagebox.showerror("Error", "Ya hay una entrada activa para este ID")
                return
            cursor.execute("INSERT INTO records (user_id, entry_time) VALUES (?, ?)", 
                          (user_id, current_time))
            self.conn.commit()
            messagebox.showinfo("Éxito", f"Entrada registrada para ID {user_id}")
            self.id_entry.delete(0, tk.END)
            self.update_records_display()
        else:
            messagebox.showerror("Error", "Por favor ingrese un ID")

    def register_exit(self):
        user_id = self.id_entry.get()
        if user_id:
            cursor = self.conn.cursor()
            current_time = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            cursor.execute("""
                SELECT id 
                FROM records 
                WHERE user_id = ? AND exit_time IS NULL 
                ORDER BY entry_time DESC 
                LIMIT 1
            """, (user_id,))
            record = cursor.fetchone()
            
            if record:
                record_id = record[0]
                cursor.execute("UPDATE records SET exit_time = ? WHERE id = ?", 
                              (current_time, record_id))
                self.conn.commit()
                messagebox.showinfo("Éxito", f"Salida registrada para ID {user_id}")
            else:
                messagebox.showwarning("Advertencia", f"No hay entradas pendientes para ID {user_id}")
            
            self.id_entry.delete(0, tk.END)
            self.update_records_display()
        else:
            messagebox.showerror("Error", "Por favor ingrese un ID")

    def register_incident(self):
        user_id = self.id_entry.get()
        if user_id:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM records WHERE user_id = ? AND exit_time IS NULL", 
                          (user_id,))
            record = cursor.fetchone()
            
            if record:
                incident_time = simpledialog.askstring("Fecha y Hora de Incidencia", 
                                                     "Ingrese la fecha y hora (dd/mm/yyyy HH:MM):", 
                                                     initialvalue="12/03/2025 14:50")
                if incident_time:
                    try:
                        datetime.datetime.strptime(incident_time, "%d/%m/%Y %H:%M")
                    except ValueError:
                        messagebox.showerror("Error", "Formato inválido. Use dd/mm/yyyy HH:MM")
                        return
                    
                    cursor.execute("INSERT INTO incidents (user_id, incident_time) VALUES (?, ?)", 
                                  (user_id, incident_time))
                    cursor.execute("UPDATE records SET exit_time = ? WHERE id = ?", 
                                  (incident_time, record[0]))
                    self.conn.commit()
                    messagebox.showinfo("Éxito", f"Incidencia registrada para ID {user_id}")
                    self.update_records_display()
            else:
                messagebox.showwarning("Advertencia", f"No hay entradas pendientes para ID {user_id}")
            self.id_entry.delete(0, tk.END)
        else:
            messagebox.showerror("Error", "Por favor ingrese un ID")

    def export_to_excel(self):
        if not self.check_admin_password():
            messagebox.showerror("Error", "Clave de administrador incorrecta")
            return
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT u.name, r.entry_time, r.exit_time 
            FROM records r 
            JOIN users u ON r.user_id = u.id
        """)
        data = cursor.fetchall()
        
        cursor.execute("""
            SELECT u.name, i.incident_time 
            FROM incidents i 
            JOIN users u ON i.user_id = u.id
        """)
        incidents = cursor.fetchall()
        
        df_records = pd.DataFrame(data, columns=['Nombre', 'Hora Entrada', 'Hora Salida'])
        df_incidents = pd.DataFrame(incidents, columns=['Nombre', 'Fecha Incidencia'])
        
        timestamp = datetime.datetime.now().strftime("%d%m%Y_%H%M%S")
        desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")  # Ruta al escritorio
        filename = os.path.join(desktop_dir, f"registros_{timestamp}.xlsx")
        
        with pd.ExcelWriter(filename) as writer:
            df_records.to_excel(writer, sheet_name='Registros', index=False)
            df_incidents.to_excel(writer, sheet_name='Incidencias', index=False)
        
        messagebox.showinfo("Éxito", f"Datos exportados a {filename}")

    def backup_db(self):
        timestamp = datetime.datetime.now().strftime("%d%m%Y_%H%M%S")
        app_data_dir = os.path.join(os.getenv('APPDATA'), 'ControlHorario')
        db_path = os.path.join(app_data_dir, 'time_tracker.db')
        backup_file = os.path.join(app_data_dir, f"backup_time_tracker_{timestamp}.db")
        shutil.copy2(db_path, backup_file)
        messagebox.showinfo("Éxito", f"Backup creado: {backup_file}")

    def update_records_display(self):
        self.records_text.delete(1.0, tk.END)
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT u.name, r.entry_time, r.exit_time 
            FROM records r 
            JOIN users u ON r.user_id = u.id 
            ORDER BY r.entry_time DESC 
            LIMIT 10
        """)
        for name, entry, exit in cursor.fetchall():
            self.records_text.insert(tk.END, 
                                   f"Nombre: {name}\nEntrada: {entry}\nSalida: {exit or 'Pendiente'}\n\n")

    def __del__(self):
        self.backup_db()
        self.conn.close()

if __name__ == "__main__":
    root = tk.Tk()
    app = TimeTrackerApp(root)
    root.mainloop()