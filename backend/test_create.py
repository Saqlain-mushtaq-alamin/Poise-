import asyncio
from app.database import SessionLocal
from app.services.ielts.conductor import IELTSSessionConductor

async def main():
    db = SessionLocal()
    conductor = IELTSSessionConductor(db)
    try:
        session = await conductor.create_session(target_band=6.5)
        print("Success:", session.id)
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
