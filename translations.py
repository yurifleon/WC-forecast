"""Spanish translations for WC Forecast.

Kept in its own module (not a giant inline dict in app.py) — a lesson from UCL
Forecast, where the inline SPANISH_TRANSLATIONS dict grew past 170 entries and
became unwieldy. Add new languages by adding a new dict + wiring it in
translate(). For a larger app, graduate to Flask-Babel / .po catalogs.
"""

SPANISH_TRANSLATIONS = {
    # Navigation / chrome
    "WC Forecast": "Quiniela Mundial",
    "Dashboard": "Panel",
    "Leaderboard": "Clasificación",
    "Bracket": "Cuadro",
    "Admin": "Admin",
    "Log in": "Ingresar",
    "Log out": "Salir",
    "Register": "Registrarse",
    "Username": "Usuario",
    "Password": "Contraseña",
    "Email": "Correo",

    # Home / auth
    "Sign in": "Iniciar sesión",
    "Create your account": "Crea tu cuenta",
    "Create your username": "Crea tu nombre de usuario",
    "Already have an account?": "¿Ya tienes cuenta?",
    "Need an account?": "¿No tienes cuenta?",
    "Welcome, {name}!": "¡Bienvenido, {name}!",
    "Invalid username or password.": "Usuario o contraseña inválidos.",
    "Username and password are required.": "El usuario y la contraseña son obligatorios.",
    "That username is taken.": "Ese usuario ya existe.",
    "Registration is full ({n} players max).": "El registro está lleno (máximo {n} jugadores).",

    # Predictions
    "Your Predictions": "Tus Pronósticos",
    "Make Prediction": "Pronosticar",
    "Update Forecast": "Actualizar Pronóstico",
    "Prediction saved.": "Pronóstico guardado.",
    "Match not found.": "Partido no encontrado.",
    "This match is not open for predictions.": "Este partido no está abierto para pronósticos.",
    "Please enter whole numbers for both scores.": "Ingresa números enteros para ambos marcadores.",
    "Scores cannot be negative.": "Los marcadores no pueden ser negativos.",
    "Pick which team advances.": "Elige qué equipo avanza.",
    "Who advances?": "¿Quién avanza?",
    "Locked": "Cerrado",
    "Open": "Abierto",
    "Deadline": "Cierre",
    "TBD": "Por definir",
    "Predict the full-time score": "Pronostica el marcador final",
    "If it goes to penalties, who advances?": "Si va a penales, ¿quién avanza?",

    # Rounds
    "Round of 32": "Dieciseisavos",
    "Round of 16": "Octavos",
    "Quarter-final": "Cuartos de final",
    "Semi-final": "Semifinal",
    "Third-place Play-off": "Tercer puesto",
    "Final": "Final",

    # Leaderboard / scoring
    "Rank": "Puesto",
    "Player": "Jugador",
    "Points": "Puntos",
    "Total": "Total",
    "Score points": "Puntos por marcador",
    "Advance points": "Puntos por avance",
    "Scoring": "Puntaje",
    "Exact score": "Marcador exacto",
    "Result + goal difference": "Resultado + diferencia de goles",
    "Result only": "Solo resultado",
    "Correct advancing team": "Equipo que avanza correcto",
    "No predictions yet.": "Aún no hay pronósticos.",
    "No players yet.": "Aún no hay jugadores.",

    # Bracket
    "Tournament Bracket": "Cuadro del Torneo",
    "Champion": "Campeón",
    "Result": "Resultado",

    # Admin
    "Admin Panel": "Panel de Admin",
    "Admin unlocked.": "Admin desbloqueado.",
    "Wrong admin password.": "Contraseña de admin incorrecta.",
    "Admin access required.": "Se requiere acceso de admin.",
    "Admin access required": "Se requiere acceso de admin",
    "Manage Matches": "Gestionar Partidos",
    "Manage Users": "Gestionar Usuarios",
    "Enter Result": "Ingresar Resultado",
    "Edit Match": "Editar Partido",
    "Save": "Guardar",
    "Home team": "Equipo local",
    "Away team": "Equipo visitante",
    "Kickoff": "Inicio",
    "Match updated.": "Partido actualizado.",
    "Result saved.": "Resultado guardado.",
    "Enter whole numbers for both scores.": "Ingresa números enteros para ambos marcadores.",
    "Add User": "Agregar Usuario",
    "User created.": "Usuario creado.",
    "Reset Password": "Restablecer Contraseña",
    "Remove": "Eliminar",
    "User removed.": "Usuario eliminado.",
    "Password for {name} set to: {pw}": "Contraseña de {name} establecida en: {pw}",
}
