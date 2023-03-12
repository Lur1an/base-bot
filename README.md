# python-telegram-bot-template
This repository serves as a template to create new [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
applications, their python wrapper over the Telegram API is amazing and enables very smooth programming for bots. 
### Foreword
I made this template to provide an implementation for a few things that I always ended up implementing in my *telegram bot* projects, custom `ApplicationContext` for `context.bot_data, context.chat_data, context.user_data` typing, decorators/wrappers for handlers to cut down on  verbose boilerplate needed to have typing support and avoid accessing dictionaries via raw strings. This will take the mind off technicalities and instead put your focus where it belongs, on the requirements and business logic.

### Configuration
The app gets its configuration from environment variables that are defined in the classes extending `pydantic.BaseSettings` in `settings.py`
```python
from pydantic import BaseSettings

class DBSettings(BaseSettings):
    MONGODB_CONNECTION_URL: str
    MONGODB_DB: str


class TelegramSettings(BaseSettings):
    BOT_TOKEN: str


class Settings(TelegramSettings, DBSettings):
    pass


settings = Settings()

```
### How to persist entities
For the persistence layer of the project I created two main template classes to extend, `MongoEntity` and `BaseDao`,
both live in `db.core`.
```python
Entity = TypeVar("Entity", bound=MongoEntity)


class BaseDAO(Generic[Entity]):
    col: AsyncIOMotorCollection
    factory: Callable[[dict], Entity]
    __collection__: ClassVar[str]

    def __init__(self, db: AsyncIOMotorDatabase):
        assert self.factory
        assert self.__collection__
        self.col = db[self.__collection__]

    async def list(self) -> AsyncIterator[Entity]:
        async for entity in self.col.find():
            yield self.factory(**entity)

    async def insert(self, entity: Entity) -> InsertOneResult:
        return await self.col.insert_one(jsonable_encoder(entity))

    async def update(self, entity: Entity) -> UpdateResult:
        return await self.col.update_one({"_id": entity.id}, {"$set": jsonable_encoder(entity)})

    async def find_by_id(self, id: str) -> Optional[Entity]:
        result = await self.col.find_one({"_id": id})
        if result:
            return self.factory(**result)

    async def exists(self, **kwargs) -> bool:
        return await self.col.count_documents(filter=kwargs)
```
Since `Generic[Entity]` is just a type helper, to actually build the objects from the dictionaries returned by the MongoDB queries you need to set the `factory` field to the actual class, and to get the collection from which you want to query the entities themselves you need to set the `__collection__` field of your class, the `__init__` method will make sure of that, failing the assertion otherwise. As I am not too familiar with python internals and metaprogramming I would love and appreciate any advice to smooth out this persistence layer.

Sample implementation:
```python
class User(MongoEntity):
    username: str

class UserDAO(BaseDAO[User]):
    __collection__ = "users"
    factory = User
```
With these few lines of code you now have access to the default CRUD implementations of the BaseDAO class, with type hints!
To add functionality look up the *[Motor documentation](https://motor.readthedocs.io/en/stable/api-asyncio/asyncio_motor_collection.html)*

```python
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


class MongoEntity(BaseModel):
    mongo_id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    @property
    def id(self) -> str:
        return str(self.mongo_id)

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            ObjectId: str,
        }
```
The data is modeled using pydantic. Any object that will be persisted to the database has to extend `MongoEntity`,
the `@property` implementation of `id` is needed because queries don't automatically convert between `ObjectId` and string. [To learn more about the power of pydantic check out their docs as well!](https://docs.pydantic.dev/)
### Application State
When you use python-telegram-bot you have access to 3 shared `dict` objects on your `context`:
1. `context.user_data`, this object is shared between all handlers that interact with updates from the same user
2. `context.chat_data`, shared between all updates for the same chat
3. `context.bot_data`, this is shared by all handlers and is useful to keep track of your shared application state

Working with raw dicts is error prone, that's why python-telegram-bot let's you define your own `CallbackContext` to replace the usual `ContextTypes.DEFAULT`. 
```python
class BotData:
    pass

class ChatData:
    pass

class UserData:
    pass

class ApplicationContext(CallbackContext[ExtBot, UserData, ChatData, BotData]):
    # Define custom @property methods here that interact with your context
    pass

```
You will find these classes in the `bot.common` module in `context.py`, you can edit the three classes above to define the state in your application depending on the context, the `ApplicationContext` class itself is used in the type signature for the context of your handlers and you can also define useful `@property` methods on it as well.

#### How are my Context classes initialized if I am only passing them as type-hints? 
To make the framework instantiate your custom objects instead of the usual dictionaries they are passed as a `ContextTypes` object to your `ApplicationBuilder`, the template takes care of this. The `Application` object itself is build inside of `bot.application`, that's also where you will need to register your handlers, either in the `on_startup` method or on the application object.
```python
context_types = ContextTypes(
    context=ApplicationContext,
    chat_data=ChatData,
    bot_data=BotData,
    user_data=UserData
)

application = ApplicationBuilder()
    .token(settings.BOT_TOKEN)
    .context_types(context_types)
    .arbitrary_callback_data(True)
    .post_init(on_startup)
    .build()
```
Now all logic defined in custom `__init__` methods will be executed and default instance variables will instantiated.
### Conversation State
As you may have noticed, the three State objects that are present in the context have user, chat and global scope. A lot of logic is implemented inside of `ConversationHandler` flows and for this custom state-management is needed, usually inside either `chat_data` or `user_data`, as most of these flows in my experience have been on a per-user basis I have provided a default to achieve this without having to add a new field to your `UserData` class for every conversation-flow that you need to implement.

```python
class UserData:
    _conversation_state: Dict[Type[ConversationState], ConversationState] = {}

    def get_conversation_state(self, cls: Type[ConversationState]) -> ConversationState:
        return self._conversation_state[cls]

    def initialize_conversation_state(self, cls: Type[ConversationState]):
        self._conversation_state[cls] = cls()

    def clean_up_conversation_state(self, conversation_type: Type[ConversationState]):
        del self._conversation_state[conversation_type]
```
The `UserData` class comes pre-defined with a dictionary to hold conversation state, the type of the object
itself is used as a key to identify it, this necessitates that for a conversation state type `T` there is at most 1 active conversation ***per user*** that uses this type for its state. 

To avoid leaking memory this object needs to be cleared from the dictionary when you are done with it, to take care of initialization and cleanup I have created two decorators:
    
```python
def init_stateful_conversation(conversation_state_type: Type[ConversationState]):
    ...

def inject_conversation_state(conversation_state_type: Type[ConversationState]):
    ...

def cleanup_stateful_conversation(conversation_state_type: Type[ConversationState]):
    ...
```
Using these you can decorate your conversation entry/exit points, to take care of the state and also inject the object into your function as an argument. `cleanup_stateful_conversation` also makes sure to catch any unexpected exceptions and return `Conversation handler.END` when it finishes.

For example, let's define an entry point handler and an exit method for a conversation flow where a user needs to follow multiple steps to fill up a `OrderRequest` object. (I will ignore the implementation details for a `ConversationHandler`, if you want to see a good example of how this works ***[click here](https://docs.python-telegram-bot.org/en/stable/examples.conversationbot.html)***)
```python
@init_stateful_conversation(OrderRequest)
async def start_order_request(update: Update, context: ApplicationContext, order_request: OrderRequest):
    ...

@inject_conversation_state(OrderRequest)
async def add_item(update: Update, context: ApplicationContext, order_request: OrderRequest):
    ...

@cleanup_stateful_conversation(OrderRequest)
async def file_order(update: Update, context: ApplicationContext, order_request: OrderRequest):
    # Complete the order, persist to database, send messages, etc...
    ...
```

### Utility decorators
```python
def admin_command(admin_ids: List[int]):
    def inner_decorator(f: Callable[[Update, ApplicationContext], Awaitable[Any]]):
        @wraps(f)
        async def wrapped(update: Update, context: ApplicationContext):
            if update.effective_user.id not in admin_ids:
                return
            return await f(update, context)

        return wrapped

    return inner_decorator
```
This decorator is used to restrict handler access to a group of users defined inside the `admin_ids` list

```python
def delete_message_after(f: Callable[[Update, ApplicationContext], Awaitable[Any]]):
    @wraps(f)
    async def wrapper(update: Update, context: ApplicationContext):
        result = await f(update, context)
        try:
            await context.bot.delete_message(
                message_id=update.effective_message.id,
                chat_id=update.effective_chat.id
            )
        finally:
            return result

    return wrapper
```
This decorator ensures your handler ***tries*** to delete the message after finishing the logic, `update.effective_message.delete()` from time to time throws exceptions even when it shouldn't, as does `bot.delete_message`, this decorator is a easy and safe way to abstract this away and make sure you tried your best to delete that message.
```python
def exit_conversation_on_exception(
        user_message: str = "I'm sorry, something went wrong, try again or contact an Administrator."
):
    def inner_decorator(f: Callable[[Update, ApplicationContext], Any]):

        @wraps(f)
        async def wrapped(update: Update, context: ApplicationContext):
            try:
                return await f(update, context)
            except:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=user_message
                )
            context.chat_data.conversation_data = None
            return ConversationHandler.END

        return wrapped

    return inner_decorator
```
This decorator catches any unchecked exceptions in your handlers inside of your conversation flow that you annotate with it and sends the poor user that had to interact with your ***(my)*** mess a message.
### CallbackQuery data injection
Arbitrary callback data is an awesome feature of *python-telegram-bot*, it increases security of your application (callback-queries are generated on the client-side and can contain malicious payloads) and makes your development workflow easier.


Since the smoothest interactions are through inline keyboards your application will be full of `CallbackQueryHandler` flows. The problem is that `callback_data` does not provide a type hint for your objects, making you write the same code over and over again to satisfy the type checker and get type hints:
```python
async def sample_handler(update: Update, context: ApplicationContext):
    my_data = cast(CustomData, context.callback_data)
    ... #do stuff
    await update.callback_query.answer()
```
I prefer using my decorator:
```python
def inject_callback_query(answer_query_after: bool = True):
    def inner_decorator(f: Callable[[Update, ApplicationContext, Generic[CallbackDataType]], Awaitable[Any]]):
        @wraps(f)
        async def wrapped(update: Update, context: ApplicationContext):
            converted_data = cast(CallbackDataType, update.callback_query.data)
            result = await f(update, context, converted_data)
            if answer_query_after:
                await update.callback_query.answer()
            return result

        return wrapped

    return inner_decorator
```
Now you can write your handler like this:
```python
@inject_callback_query
async def sample_handler(update: Update, context: ApplicationContext, my_data: CustomData):
    ... #do stuff
```
Since we are interacting with our `CustomData` type in our `CallbackQueryHandler` most of the time we only have 1 handler for this defined Callback Type and always end up writing:
```python
custom_data_callback_handler = CallbackQueryHandler(callback=sample_handler, pattern=CustomData)
```
I added another decorator to turn the wrapped function directly into a `CallbackQueryHandler`:
```python
def arbitrary_callback_query_handler(query_data_type: CallbackDataType, answer_query_after: bool = True):
    def inner_decorator(
            f: Callable[[Update, ApplicationContext, Generic[CallbackDataType]], Awaitable[Any]]
    ) -> CallbackQueryHandler:
        decorator = inject_callback_query(answer_query_after=answer_query_after)
        wrapped = decorator(f)
        handler = CallbackQueryHandler(pattern=query_data_type, callback=wrapped)
        return handler

    return inner_decorator
```
This will take care of instantiating your `CallbackQueryHandler`, putting this together with the above sample we can write it like this:
```python
@arbitrary_callback_query_handler(CustomData)
async def sample_handler(update: Update, context: ApplicationContext, my_data: CustomData):
    ... #do stuff
```
Keep in mind that this approach is a bit limited if you want to handle types of `CustomData` callback queries differently depending on other patterns like chat or message content, python-telegram-bot lets you combine patterns together with binary logic operators, as I have rarely used this I have not added parameters to the decorator for this case, I might in the future. Since this is just a template you can also do it yourself for your project!