import asyncio
import json
import logging
import os
from aiokafka import AIOKafkaConsumer

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
KAFKA_GROUP = "notification-service"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [notification] %(message)s")
log = logging.getLogger(__name__)

HANDLERS = {
    "property.status_changed": lambda p: log.info(
        "Property %d status changed: %s → %s", p["id"], p["old_status"], p["new_status"]
    ),
    "viewing.scheduled": lambda p: log.info(
        "Viewing %d scheduled for property %d by buyer %d at %s",
        p["id"], p["property_id"], p["buyer_id"], p["scheduled_at"],
    ),
}


async def consume():
    consumer = AIOKafkaConsumer(
        "real-estate.properties", "real-estate.viewings",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=KAFKA_GROUP,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda v: json.loads(v.decode()),
    )
    await consumer.start()
    log.info("Notification service started")
    try:
        async for msg in consumer:
            event = msg.value
            handler = HANDLERS.get(event.get("event_type"))
            if handler:
                try:
                    handler(event.get("payload", {}))
                except Exception as e:
                    log.error("Handler error: %s", e)
            await consumer.commit()
    finally:
        await consumer.stop()


if __name__ == "__main__":
    asyncio.run(consume())
