SYNC_THRESHOLD = 600  # seconds


# async def get_current_user(request: Request, db: Session):
#     """
#     Lazy-upsert DB user with threshold, uses auth_user from middleware
#     """
#     auth_user = get_auth_user(request)
#     user_id = auth_user["id"]

#     stmt = select(User).where(User.id == user_id)
#     user = db.exec(stmt).first()
#     now = datetime.utcnow()

#     if not user:
#         user = User(id=user_id, email=auth_user.get("email"), last_seen=now)
#         db.add(user)
#     else:
#         if (now - user.last_seen).total_seconds() > SYNC_THRESHOLD:
#             user.last_seen = now
#             if auth_user.get("email") and user.email != auth_user["email"]:
#                 user.email = auth_user["email"]
#     db.commit()
#     db.refresh(user)
#     return user
