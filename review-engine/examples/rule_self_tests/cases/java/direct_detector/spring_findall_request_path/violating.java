import org.springframework.web.bind.annotation.RestController; @RestController class Demo { void list() { repository.findAll(); } }
