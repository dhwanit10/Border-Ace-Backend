# from app.core.database import engine, Base
# from app.models import (
#     User, Document, 
#     VerificationEntry, Risk, System, Session
# )

# def createTables():
#     print("Creating tables...")
#     Base.metadata.create_all(bind=engine)
#     print("✅ Tables created successfully!")

import os
from datetime import datetime

# from dotenv import load_dotenv
from app.core.config import settings
from app.core.database import Base, engine, SessionLocal
from app.core.security import hash_password

from app.models.user import User, UserType, UserStatus
from app.models.system import System, SystemStatus




def initialize_database():

    print("Creating tables...")

    # 1. Create tables
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:

        # -----------------------------------------
        # CHECK BOOTSTRAP ADMIN
        # -----------------------------------------

        admin = (
            db.query(User)
            .filter(
                User.username == settings.BOOTSTRAP_ADMIN_USERNAME
            )
            .first()
        )

        if not admin:

            print("Creating bootstrap admin...")

            face_image = None

            if (
                settings.BOOTSTRAP_ADMIN_FACE_IMAGE
                and os.path.exists(
                    settings.BOOTSTRAP_ADMIN_FACE_IMAGE
                )
            ):
                with open(
                    settings.BOOTSTRAP_ADMIN_FACE_IMAGE,
                    "rb"
                ) as file:
                    face_image = file.read()

            admin = User(

                username=settings.BOOTSTRAP_ADMIN_USERNAME,

                password_hash=hash_password(
                    settings.BOOTSTRAP_ADMIN_PASSWORD
                ),

                full_name=settings.BOOTSTRAP_ADMIN_NAME,

                dob=datetime.strptime(
                    settings.BOOTSTRAP_ADMIN_DOB,
                    "%Y-%m-%d"
                ).date(),

                gender=settings.BOOTSTRAP_ADMIN_GENDER,

                aadhar_no=settings.BOOTSTRAP_ADMIN_AADHAR,

                phone=settings.BOOTSTRAP_ADMIN_PHONE,

                email=settings.BOOTSTRAP_ADMIN_EMAIL,

                face_image=face_image,

                user_type=UserType.ADMIN,

                status=UserStatus.OFFLINE
            )

            db.add(admin)
            db.commit()
            db.refresh(admin)

            print(
                f"Bootstrap admin created: {admin.username}"
            )

        else:

            print(
                f"Bootstrap admin already exists: "
                f"{admin.username}"
            )


        # -----------------------------------------
        # CHECK BOOTSTRAP SYSTEM
        # -----------------------------------------

        system = (
            db.query(System)
            .filter(
                System.system_name ==
                settings.BOOTSTRAP_SYSTEM_NAME
            )
            .first()
        )

        if not system:

            print("Creating bootstrap system...")

            system = System(

                system_name=settings.BOOTSTRAP_SYSTEM_NAME,

                status=SystemStatus.OFFLINE,

                primary_owner_id=admin.id
            )

            db.add(system)
            db.commit()
            db.refresh(system)

            print(
                f"Bootstrap system created: "
                f"{system.system_name}"
            )

        else:

            print(
                f"Bootstrap system already exists: "
                f"{system.system_name}"
            )

        print("Database initialization completed.")

    except Exception:

        db.rollback()
        raise

    finally:

        db.close()