# 🎬 Movie Rental Platform

A full-stack movie rental web application designed with a product-oriented approach.  
The system supports role-based access, dynamic movie management, and a clean user interface inspired by modern streaming platforms.

---

## 📌 Overview

This project simulates a real-world movie rental platform where users can browse, rent, and manage movies, while administrators control the catalog and pricing.

The application focuses on:
- clean architecture  
- practical feature implementation  
- real-world usability  

---

## 🚀 Core Features

### 👤 User Side
- Browse movies with posters and details  
- Rent and return movies  
- Search movies by title  
- Filter movies by genre  
- View rental history  
- Rate movies  
- Add movies to watchlist  

---

### 🛠️ Admin Panel
- Add new movies with image upload  
- Update movie details and pricing (₹)  
- Delete movies from catalog  
- View system analytics (most rented movies)  

---

## ⚙️ Technical Design

### Backend
- Flask (modular structure using Blueprints)
- REST-style routing
- Role-based access control

### Database
- SQLite with relational schema:
  - Users  
  - Movies  
  - Rentals  
  - Watchlist  

### Frontend
- HTML + CSS + JavaScript  
- Dynamic filtering (search + genre)  
- Responsive movie card layout  

---

## 💡 Key Functional Highlights

- Real-time availability tracking  
- Genre-based recommendation system  
- Image upload & rendering  
- Currency localized to INR (₹)  
- Clean separation of admin and user flows  

---

## 📂 Project Structure
MovieRental/

│├── app.py

├── models.py

├── routes/

├── templates/

├── static/

│ ├── uploads/

│ └── css/

├── requirements.txt



---

## 🛠️ Setup Instructions

```bash
git clone https://github.com/knVeerendra/MovieRental.git
cd MovieRental
pip install -r requirements.txt
python app.py


Access:
http://127.0.0.1:5000

🔐 Admin Access
Email: admin@example.com  
Password: admin123
