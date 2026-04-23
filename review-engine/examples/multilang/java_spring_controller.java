import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Transactional
class UserController {
    @Autowired
    private UserRepository userRepository;

    @GetMapping("/users")
    public Object listUsers() {
        return userRepository.findAll();
    }
}
