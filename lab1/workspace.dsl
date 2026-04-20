workspace {
    name "Система управления недвижимостью"
    description "Система для поиска, публикации и записи на просмотр объектов недвижимости (аналог Zillow). Вариант 24."

    !identifiers hierarchical

    model {
        buyer = person "Покупатель / Арендатор" {
            description "Поиск объектов недвижимости по городу и цене, запись на просмотр."
        }

        agent = person "Агент / Владелец" {
            description "Публикация объектов недвижимости, управление статусами объектов."
        }

        admin = person "Администратор" {
            description "Управление пользователями, объектами и просмотрами. Полный доступ к системе."
        }

        notificationGateway = softwareSystem "Система уведомлений" {
            description "Внешний сервис отправки email и SMS уведомлений о записи на просмотр."
        }

        realEstateSystem = softwareSystem "Система управления недвижимостью" {
            description "Управление пользователями, объектами недвижимости и просмотрами."

            authService = container "Auth Service" {
                technology "Python, FastAPI, JWT"
                description "Аутентификация, авторизация (JWT), управление пользователями. Роли: ADMIN, AGENT, BUYER."
            }

            propertyService = container "Property Service" {
                technology "Python, FastAPI"
                description "Управление объектами недвижимости и записями на просмотр. Авторизует запросы через Auth Service."
            }

            database = container "Database" {
                technology "PostgreSQL"
                description "Хранение пользователей, объектов недвижимости и записей на просмотр."
                tags "Database"
            }

            authService -> database "Читает и записывает данные о пользователях" "SQL/asyncpg"
            propertyService -> database "Читает и записывает объекты и просмотры" "SQL/asyncpg"
            propertyService -> authService "Верификация JWT токена" "HTTP"
            notificationService = container "Notification Service" {
                technology "Python, aiokafka"
                description "Kafka-консьюмер событий. В production отправляет email/SMS уведомления о записи на просмотр."
            }

            propertyService -> notificationService "Публикация события в Kafka" "Kafka"
            notificationService -> notificationGateway "Отправка email/SMS уведомления" "HTTP"
        }

        buyer -> realEstateSystem.authService "Регистрация и получение JWT токена" "HTTPS"
        buyer -> realEstateSystem.propertyService "Поиск объектов, запись на просмотр" "HTTPS"

        agent -> realEstateSystem.authService "Получение JWT токена" "HTTPS"
        agent -> realEstateSystem.propertyService "Публикация объектов, изменение статуса" "HTTPS"

        admin -> realEstateSystem.authService "Управление пользователями" "HTTPS"
        admin -> realEstateSystem.propertyService "Управление объектами и просмотрами" "HTTPS"
    }

    views {
        systemContext realEstateSystem "SystemContext" {
            include *
            autolayout lr
        }

        container realEstateSystem "Containers" {
            include *
            autolayout lr
        }

        dynamic realEstateSystem "createUser" "Создание нового пользователя" {
            admin -> realEstateSystem.authService "POST /users"
            realEstateSystem.authService -> realEstateSystem.database "INSERT INTO users"
            autolayout lr
        }

        dynamic realEstateSystem "addProperty" "Добавление объекта недвижимости" {
            agent -> realEstateSystem.propertyService "POST /properties"
            realEstateSystem.propertyService -> realEstateSystem.authService "Проверка JWT и роли AGENT"
            realEstateSystem.propertyService -> realEstateSystem.database "INSERT INTO properties"
            autolayout lr
        }

        dynamic realEstateSystem "scheduleViewing" "Запись на просмотр объекта" {
            buyer -> realEstateSystem.propertyService "POST /viewings"
            realEstateSystem.propertyService -> realEstateSystem.authService "Проверка JWT и роли BUYER"
            realEstateSystem.propertyService -> realEstateSystem.database "INSERT INTO viewings"
            realEstateSystem.propertyService -> realEstateSystem.notificationService "Событие viewing.scheduled (Kafka)"
            realEstateSystem.notificationService -> notificationGateway "Отправка email/SMS уведомления"
            autolayout lr
        }

        theme default
    }
}
