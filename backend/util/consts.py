# max bytes size
MAX_UPLOAD = 150 * 1024 * 1024

# only zips allowed for upload
UPLOAD_EXT = {".zip"}

# maps extensions to languages
EXTENSIONS = {
    ".py" : "Python",
    ".js" : "Javascript",
    ".ts" : "Typescript",
    ".c" : "C",
    ".cpp" : "C++",
    ".go" : "Go",
    ".java" : "Java",
    ".rb" : "Ruby",
    ".html" : "HTML",
    ".css" : "CSS",
    ".cs" : "C#",
    ".swift" : "Swift",
    ".rs" : "Rust",
    ".php" : "PHP"
}

# maps frameworks to keywords
FRAMEWORKS = {
    "django": ["django"],
    "fastapi": ["fastapi"],
    "flask": ["flask"],
    "express": ["express"],
    "react": ["react", "create-react-app"],
    "nextjs": ["next", "next.config"],
    "vue": ["vue"],
    "angular": ["@angular"],
    "spring": ["spring", "springboot"],
    "rails": ["rails", "active_record"],
}

# maps packages to keywords
PACKAGES = {
    "npm": ["package.json", "package-lock.json", "yarn.lock"],
    "pip": ["requirements.txt", "pyproject.toml", "Pipfile"],
    "go": ["go.mod"],
    "cargo": ["Cargo.toml"],
}
