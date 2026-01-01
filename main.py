import random
import time
import toml
import urllib.parse
import rnet  

from rnet import blocking, EmulationOption  
from concurrent.futures import ThreadPoolExecutor, as_completed
from logmagix import Logger, Home
from functools import wraps

config = toml.load("input/config.toml")

DEBUG = config['dev'].get('Debug', False)

log = Logger()

def debug(func_or_message, *args, **kwargs) -> callable:
    if callable(func_or_message):
        @wraps(func_or_message)
        def wrapper(*args, **kwargs):
            result = func_or_message(*args, **kwargs)
            if DEBUG:
                log.debug(f"{func_or_message.__name__} returned: {result}")
            return result
        return wrapper
    else:
        if DEBUG:
            log.debug(f"Debug: {func_or_message}")

def debug_response(response: rnet.Response) -> None:
    debug(response.headers)
    try:
        debug(response.text())
    except:
        debug(response.bytes())
    debug(response.status)

class Miscllaneous:
    @debug
    def get_proxies(self) -> rnet.Proxy:
        try:
            if config['dev'].get('Proxyless', False):
                return None
                
            with open('input/proxies.txt') as f:
                proxies = [line.strip() for line in f if line.strip()]
                if not proxies:
                    log.warning("No proxies available. Running in proxyless mode.")
                    return None
                
                proxy_choice = random.choice(proxies)
                debug(f"Using proxy: {proxy_choice}")
                
                return rnet.Proxy.all("http://" + proxy_choice)
        except FileNotFoundError:
            log.failure("Proxy file not found. Running in proxyless mode.")
            return None

    @debug
    def randomize_user_agent(self) -> tuple[str, str, str, str]:
        platforms = {
            "Windows NT 10.0; Win64; x64": "Windows",
            "Windows NT 10.0; WOW64": "Windows",
            "Macintosh; Intel Mac OS X 10_15_7": "Mac OS X",
            "Macintosh; Intel Mac OS X 11_2_3": "Mac OS X",
            "X11; Linux x86_64": "Linux",
            "X11; Linux i686": "Linux",
            "X11; Ubuntu; Linux x86_64": "Linux",
        }

        browsers = [
            ("Chrome", f"{random.randint(128, 140)}.0.{random.randint(1000, 4999)}.0"),
            ("Firefox", f"{random.randint(80, 115)}.0"),
            ("Safari", f"{random.randint(13, 16)}.{random.randint(0, 3)}"),
            ("Edge", f"{random.randint(90, 140)}.0.{random.randint(1000, 4999)}.0"),
        ]

        webkit_version = f"{random.randint(500, 600)}.{random.randint(0, 99)}"
        platform_string = random.choice(list(platforms.keys()))
        browser_name, browser_version = random.choice(browsers)

        if browser_name == "Safari":
            user_agent = (
                f"Mozilla/5.0 ({platform_string}) AppleWebKit/{webkit_version} (KHTML, like Gecko) "
                f"Version/{browser_version} Safari/{webkit_version}"
            )
        elif browser_name == "Firefox":
            user_agent = f"Mozilla/5.0 ({platform_string}; rv:{browser_version}) Gecko/20100101 Firefox/{browser_version}"
        else: # Chrome or Edge
            user_agent = (
                f"Mozilla/5.0 ({platform_string}) AppleWebKit/{webkit_version} (KHTML, like Gecko) "
                f"{browser_name}/{browser_version} Safari/{webkit_version}"
            )

        return user_agent
    
class Viewbot:
    def __init__(self, misc: Miscllaneous, user: str, proxy: rnet.Proxy = None) -> None:
        self.session = blocking.Client(  
            emulation=EmulationOption.random(),
            headers = {
                'accept': '*/*',
                'accept-language': 'fr-FR,fr;q=0.9',
                'content-type': 'application/json',
                'origin': 'https://e.rich',
                'priority': 'u=1, i',
                'referer': 'https://e.rich/',
                'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': misc.randomize_user_agent(),
            },
            proxy = proxy 
        )
        
        self.user = user
    
    @debug
    def get_views(self, response: rnet.Response = None) -> int:
        if response is None:
            response = self.session.get(f'https://api.e.rich/api/users/profile/{self.user}')
            debug_response(response)
            
        if response.status.as_int() == 200:
            views = response.json()["user"].get("profile_views", 0)
            return views
        else:
            log.failure(f"Failed to get views for user: {self.user} - {response.text()} {response.status.as_int()}")
            return 0
    
    @debug
    def send_views(self) -> rnet.Response | None:
        response = self.session.get(f'https://api.e.rich/api/users/profile/{self.user}')
        
        debug_response(response)
        
        if response.status.as_int() == 200:
            return response
        else:
            log.failure(f"Failed to send view to user: {self.user} - {response.text()} {response.status.as_int()}")
        
        return None

@debug
def worker(misc: Miscllaneous, user: str, target_views: int = 0) -> None:
    bot = Viewbot(misc, user, misc.get_proxies())
    try:         
        initial_views = bot.get_views()
        views_sent = 0
        
        while views_sent < target_views or not target_views:
            start = time.time()
            
            response = bot.send_views()
            if response:
                views_sent += 1
                current_views = bot.get_views(response)
                log.message("e.rich" , f"Successfully sent view - Current views: {current_views}", start=start, end=time.time())
                
    except KeyboardInterrupt:
        log.info(f"User interrupted the process - Initial views: {initial_views}, Views sent: {views_sent}, Current views: {current_views}")
        
def main() -> None:
    try:
        misc = Miscllaneous()
        
        banner = Home("Erich View Bot", align="center", credits="discord.cyberious.xyz")
        banner.display()
        
        user = config['data'].get('user', '')
        threads = config["dev"].get("Threads")
        
        if "http" in user or "www" in user:
            parsed_url = urllib.parse.urlparse(user)
            user = parsed_url.path.strip("/").split("/")[-1]

        target_views = config['data'].get('views', 0)
        
        if not user:
            log.critical("No user specified in config.toml")
            return
            
        bot = Viewbot(misc, user)
        log.info(f"Current Views: {bot.get_views()} - Target Views: {target_views if target_views else 'Unlimited'}")
        
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = []
            for _ in range(threads):  
                future = executor.submit(worker, misc, user, target_views)
                futures.append(future)
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    log.failure(f"Thread failed: {e}")
            
    except Exception as e:
        log.critical(f"An error occurred: {e}")
if __name__ == "__main__":
    main()